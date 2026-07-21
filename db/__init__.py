import contextvars
import json
import uuid
from datetime import datetime, timedelta
from functools import wraps

from db.backend import DBBackend
from db.sqlite import SQLiteBackend

_backend: DBBackend = SQLiteBackend()

_PRIORITY_GAP = 1000

# Соединение, общее для всех db.*-вызовов в пределах одного HTTP-запроса (см. request-scoped
# middleware в support_planner.py) — по умолчанию None, т.е. вне запроса (импорт модуля,
# seed_demo_data.py) with_db_connection продолжает открывать и закрывать своё соединение на
# каждый вызов, как и раньше.
_request_conn: 'contextvars.ContextVar' = contextvars.ContextVar('request_conn', default=None)


def set_request_connection(conn):
    """Установить соединение, общее для текущего запроса. Возвращает Token для clear_request_connection."""
    return _request_conn.set(conn)


def clear_request_connection(token):
    """Снять соединение, общее для текущего запроса (вызывается в finally у request-scoped middleware)."""
    _request_conn.reset(token)


class IntegrityConstraintError(Exception):
    """Обёртка над ошибкой нарушения констрейнта БД (дубль уникального имени, попытка удалить
    запись, на которую ещё ссылаются другие) с уже готовым для показа пользователю сообщением."""
    pass


class BulkAssignmentRescheduleError(Exception):
    """Ошибка проверки атомарного переноса нескольких назначений."""

    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code


def get_db_connection():
    conn = _backend.connect()
    _backend.setup_connection(conn)
    return conn


def with_db_connection(default_return=None, raise_on_error=True, commit_on_success=True):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            shared_conn = _request_conn.get()
            conn = shared_conn if shared_conn is not None else get_db_connection()
            try:
                result = func(conn, *args, **kwargs)
                if commit_on_success:
                    conn.commit()
                return result
            except _backend.db_error:
                conn.rollback()
                if raise_on_error:
                    raise
                return default_return
            finally:
                if shared_conn is None:
                    conn.close()

        return wrapper

    return decorator


@with_db_connection()
def init_db(conn):
    _backend.init_schema(conn)


# === TEAMS CRUD ===
@with_db_connection(commit_on_success=False)
def get_all_teams(conn):
    """Получить все команды"""
    return conn.execute('SELECT id, name FROM teams ORDER BY name').fetchall()


@with_db_connection(commit_on_success=False)
def get_all_teams_with_templates(conn):
    """Получить все команды вместе с разрешёнными шаблонами блоков"""
    teams = conn.execute('SELECT id, name FROM teams ORDER BY name').fetchall()
    rows = conn.execute(
        '''SELECT tt.team_id, bt.id, bt.name
           FROM team_templates tt
           JOIN block_templates bt ON tt.template_id = bt.id
           ORDER BY bt.name'''
    ).fetchall()

    tmpls_by_team = {}
    for r in rows:
        tmpls_by_team.setdefault(r['team_id'], []).append({'id': r['id'], 'name': r['name']})

    return [{'id': t['id'], 'name': t['name'], 'templates': tmpls_by_team.get(t['id'], [])} for t in teams]


@with_db_connection(commit_on_success=False)
def get_teams_for_user(conn, user_id, role):
    if role == 'admin' or not conn.execute(
        'SELECT 1 FROM user_team_access WHERE user_id = ? LIMIT 1', (user_id,)
    ).fetchone():
        teams = conn.execute('SELECT id, name FROM teams ORDER BY name').fetchall()
    else:
        teams = conn.execute(
            '''SELECT t.id, t.name FROM teams t
               JOIN user_team_access access ON access.team_id = t.id
               WHERE access.user_id = ? ORDER BY t.name''', (user_id,)
        ).fetchall()
    rows = conn.execute(
        '''SELECT tt.team_id, bt.id, bt.name FROM team_templates tt
           JOIN block_templates bt ON tt.template_id = bt.id ORDER BY bt.name'''
    ).fetchall()
    templates = {}
    allowed = {team['id'] for team in teams}
    for row in rows:
        if row['team_id'] in allowed:
            templates.setdefault(row['team_id'], []).append({'id': row['id'], 'name': row['name']})
    return [{'id': team['id'], 'name': team['name'], 'templates': templates.get(team['id'], [])} for team in teams]


@with_db_connection(commit_on_success=False)
def get_teams_page_for_user(conn, user_id, role, offset=0, limit=20, search=None):
    """Вернуть страницу доступных пользователю команд с разрешёнными шаблонами."""
    needle = (search or '').strip().casefold()
    restricted = role != 'admin' and conn.execute(
        'SELECT 1 FROM user_team_access WHERE user_id = ? LIMIT 1', (user_id,)
    ).fetchone()

    joins = ''
    where = []
    params = []
    if restricted:
        joins = 'JOIN user_team_access access ON access.team_id = t.id'
        where.append('access.user_id = ?')
        params.append(user_id)
    if needle:
        where.append('instr(casefold(t.name), ?) > 0')
        params.append(needle)

    where_clause = f"WHERE {' AND '.join(where)}" if where else ''
    total = conn.execute(
        f'SELECT COUNT(*) FROM teams t {joins} {where_clause}', tuple(params)
    ).fetchone()[0]
    teams = conn.execute(
        f'''SELECT t.id, t.name FROM teams t
            {joins}
            {where_clause}
            ORDER BY t.name
            LIMIT ? OFFSET ?''',
        (*params, limit, offset),
    ).fetchall()

    templates = {}
    team_ids = [team['id'] for team in teams]
    if team_ids:
        placeholders = ','.join('?' * len(team_ids))
        rows = conn.execute(
            f'''SELECT tt.team_id, bt.id, bt.name FROM team_templates tt
                JOIN block_templates bt ON tt.template_id = bt.id
                WHERE tt.team_id IN ({placeholders})
                ORDER BY bt.name''',
            team_ids,
        ).fetchall()
        for row in rows:
            templates.setdefault(row['team_id'], []).append({'id': row['id'], 'name': row['name']})

    return {
        'teams': [
            {'id': team['id'], 'name': team['name'], 'templates': templates.get(team['id'], [])}
            for team in teams
        ],
        'total': total,
    }


@with_db_connection()
def grant_team_access_if_restricted(conn, user_id, role, team_id):
    if role == 'admin':
        return
    if conn.execute('SELECT 1 FROM user_team_access WHERE user_id = ? LIMIT 1', (user_id,)).fetchone():
        conn.execute('INSERT OR IGNORE INTO user_team_access (user_id, team_id) VALUES (?, ?)', (user_id, team_id))


@with_db_connection(commit_on_success=False)
def get_team_by_id(conn, team_id):
    """Получить команду по ID"""
    return conn.execute('SELECT id, name FROM teams WHERE id = ?', (team_id,)).fetchone()


@with_db_connection(commit_on_success=False)
def get_team_allowed_templates(conn, team_id):
    """Получить шаблоны, разрешённые для команды, вместе с блоками, смещениями и сегментом шаблона
    (segment_id включён в каждый шаблон, чтобы клиент мог сузить список до сегмента конкретной
    задачи — см. AssignmentModal.tsx)"""
    tmpls = conn.execute(
        '''SELECT bt.id, bt.name, bt.segment_id
           FROM team_templates tt
           JOIN block_templates bt ON tt.template_id = bt.id
           WHERE tt.team_id = ?
           ORDER BY bt.name''',
        (team_id,)
    ).fetchall()

    result = []
    for t in tmpls:
        result.append({
            'id': t['id'],
            'name': t['name'],
            'segment_id': t['segment_id'],
            'blocks': _get_template_blocks(conn, t['id'])
        })
    return result


@with_db_connection(commit_on_success=False)
def get_blocks_for_team(conn, team_id, segment_id=None):
    """Получить уникальные блоки из разрешённых шаблонов команды, опционально ограниченные
    шаблонами конкретного сегмента"""
    segment_clause = 'AND bt.segment_id = ?' if segment_id is not None else ''
    params = [team_id] + ([segment_id] if segment_id is not None else [])
    rows = conn.execute(
        f'''SELECT DISTINCT b.id, b.name
            FROM team_templates tt
            JOIN block_templates bt ON tt.template_id = bt.id
            JOIN template_blocks tb ON tt.template_id = tb.template_id
            JOIN blocks b ON tb.block_id = b.id
            WHERE tt.team_id = ?
            {segment_clause}
            ORDER BY b.name ASC''',
        params
    ).fetchall()
    return [{'id': r['id'], 'name': r['name']} for r in rows]


def _set_team_templates(conn, team_id, template_ids):
    """Заменить набор разрешённых шаблонов команды (без коммита)"""
    conn.execute('DELETE FROM team_templates WHERE team_id = ?', (team_id,))
    for tmpl_id in (template_ids or []):
        try:
            conn.execute(
                'INSERT OR IGNORE INTO team_templates (team_id, template_id) VALUES (?, ?)',
                (team_id, int(tmpl_id))
            )
        except (TypeError, ValueError):
            pass


@with_db_connection()
def create_team(conn, name, template_ids=None):
    """Создать команду"""
    try:
        cursor = conn.execute('INSERT INTO teams (name) VALUES (?)', (name,))
    except _backend.duplicate_error:
        raise IntegrityConstraintError('Команда с таким названием уже существует')
    team_id = _backend.last_insert_id(cursor)
    _set_team_templates(conn, team_id, template_ids)
    return team_id


@with_db_connection()
def update_team(conn, team_id, name, template_ids=None):
    """Обновить команду и её разрешённые шаблоны"""
    try:
        conn.execute('UPDATE teams SET name = ? WHERE id = ?', (name, team_id))
    except _backend.duplicate_error:
        raise IntegrityConstraintError('Команда с таким названием уже существует')
    _set_team_templates(conn, team_id, template_ids)


@with_db_connection()
def delete_team(conn, team_id):
    """Удалить команду (шаблоны и задачи удаляются каскадно — team_templates.team_id и tasks.team_id
    оба ON DELETE CASCADE, поэтому в отличие от delete_segment здесь физически не может возникнуть
    нарушение внешнего ключа)"""
    conn.execute('DELETE FROM teams WHERE id = ?', (team_id,))


# === SEGMENTS CRUD ===
@with_db_connection(commit_on_success=False)
def get_all_segments(conn):
    """Получить все сегменты"""
    rows = conn.execute('SELECT id, name FROM segments ORDER BY name').fetchall()
    return [{'id': r['id'], 'name': r['name']} for r in rows]


@with_db_connection()
def create_segment(conn, name):
    """Создать сегмент"""
    try:
        cursor = conn.execute('INSERT INTO segments (name) VALUES (?)', (name.strip(),))
    except _backend.duplicate_error:
        raise IntegrityConstraintError('Сегмент с таким названием уже существует')
    return _backend.last_insert_id(cursor)


@with_db_connection()
def update_segment(conn, segment_id, name):
    """Обновить сегмент"""
    try:
        conn.execute('UPDATE segments SET name = ? WHERE id = ?', (name.strip(), segment_id))
    except _backend.duplicate_error:
        raise IntegrityConstraintError('Сегмент с таким названием уже существует')


@with_db_connection()
def delete_segment(conn, segment_id):
    """Удалить сегмент. Падает с IntegrityConstraintError, если сегмент ещё используется в tasks/
    block_templates (FK без ON DELETE) — маршрут превращает это в 400, как и для blocks/teams."""
    try:
        conn.execute('DELETE FROM segments WHERE id = ?', (segment_id,))
    except _backend.duplicate_error:
        raise IntegrityConstraintError('Нельзя удалить сегмент: он используется в задачах или шаблонах блоков')


# === BLOCKS CRUD ===
@with_db_connection(commit_on_success=False)
def get_all_blocks(conn):
    """Получить все блоки"""
    rows = conn.execute('SELECT id, name FROM blocks ORDER BY name').fetchall()
    return [{'id': r['id'], 'name': r['name']} for r in rows]


@with_db_connection()
def create_block(conn, name):
    """Создать блок"""
    name = name.strip().upper()
    try:
        cursor = conn.execute('INSERT INTO blocks (name) VALUES (?)', (name,))
    except _backend.duplicate_error:
        raise IntegrityConstraintError('Блок с таким названием уже существует')
    return _backend.last_insert_id(cursor)


@with_db_connection()
def delete_block(conn, block_id):
    """Удалить блок (template_blocks.block_id — ON DELETE CASCADE, поэтому удаление автоматически
    убирает блок из всех шаблонов; физически не может нарушить внешний ключ)"""
    conn.execute('DELETE FROM blocks WHERE id = ?', (block_id,))


# === BLOCK TEMPLATES CRUD ===
def _get_template_blocks(conn, template_id):
    """Блоки шаблона (id, name, shift_days), упорядоченные по смещению и имени — общий запрос для
    get_all_templates/get_template_by_id/get_team_allowed_templates."""
    blocks = conn.execute(
        '''SELECT b.id, b.name, tb.schedule_offset AS shift_days
           FROM template_blocks tb
           JOIN blocks b ON tb.block_id = b.id
           WHERE tb.template_id = ?
           ORDER BY tb.schedule_offset ASC, b.name ASC''',
        (template_id,)
    ).fetchall()
    return [{'id': b['id'], 'name': b['name'], 'shift_days': b['shift_days']} for b in blocks]


@with_db_connection(commit_on_success=False)
def get_all_templates(conn):
    """Получить все шаблоны блоков с их блоками, смещениями и сегментом"""
    tmpls = conn.execute('SELECT id, name, segment_id FROM block_templates ORDER BY name').fetchall()
    result = []
    for t in tmpls:
        result.append({
            'id': t['id'],
            'name': t['name'],
            'segment_id': t['segment_id'],
            'blocks': _get_template_blocks(conn, t['id'])
        })
    return result


@with_db_connection(commit_on_success=False)
def get_template_by_id(conn, template_id):
    """Получить шаблон по ID с блоками и сегментом"""
    t = conn.execute('SELECT id, name, segment_id FROM block_templates WHERE id = ?', (template_id,)).fetchone()
    if not t:
        return None
    return {
        'id': t['id'],
        'name': t['name'],
        'segment_id': t['segment_id'],
        'blocks': _get_template_blocks(conn, template_id)
    }


def _set_template_blocks(conn, template_id, entries):
    """Заменить блоки шаблона (без коммита). entries=[{block_id, shift_days}]"""
    conn.execute('DELETE FROM template_blocks WHERE template_id = ?', (template_id,))
    for e in (entries or []):
        try:
            block_id = int(e.get('block_id'))
            shift_days = int(e.get('shift_days', 0) or 0)
        except (TypeError, ValueError):
            continue
        conn.execute(
            'INSERT OR IGNORE INTO template_blocks (template_id, block_id, schedule_offset) VALUES (?, ?, ?)',
            (template_id, block_id, shift_days)
        )


@with_db_connection()
def create_template(conn, name, segment_id, entries=None):
    """Создать шаблон блоков"""
    try:
        cursor = conn.execute(
            'INSERT INTO block_templates (name, segment_id) VALUES (?, ?)', (name.strip(), segment_id)
        )
    except _backend.duplicate_error:
        raise IntegrityConstraintError('Шаблон с таким названием уже существует')
    template_id = _backend.last_insert_id(cursor)
    _set_template_blocks(conn, template_id, entries)
    return template_id


@with_db_connection()
def update_template(conn, template_id, name, segment_id, entries=None):
    """Обновить шаблон и его блоки"""
    try:
        conn.execute(
            'UPDATE block_templates SET name = ?, segment_id = ? WHERE id = ?', (name.strip(), segment_id, template_id)
        )
    except _backend.duplicate_error:
        raise IntegrityConstraintError('Шаблон с таким названием уже существует')
    _set_template_blocks(conn, template_id, entries)


@with_db_connection()
def delete_template(conn, template_id):
    """Удалить шаблон (записи template_blocks и team_templates удаляются каскадно — оба ON DELETE
    CASCADE на template_id, поэтому физически не может нарушить внешний ключ)"""
    conn.execute('DELETE FROM block_templates WHERE id = ?', (template_id,))


# === USERS CRUD ===
@with_db_connection(commit_on_success=False)
def user_exists(conn, user_id):
    """Проверить существование пользователя и получить его роль (используется для валидации сессии
    в require_login — сессия может пережить удаление пользователя или пересоздание БД)"""
    return conn.execute('SELECT role FROM users WHERE id = ?', (user_id,)).fetchone()


# Логин учётной записи-бутстрапа, создаваемой init_schema() при первом запуске (см. CLAUDE.md) —
# у неё всегда должен оставаться рабочий вход в систему, поэтому её нельзя удалить через UI/API.
# Идентификация по login, а не по ФИО: с тех пор как ФИО перестали быть уникальными, обычный
# пользователь мог бы случайно (или намеренно) совпасть по имени с бутстрап-записью — login же
# по-прежнему защищён UNIQUE-индексом, так что это единственный надёжный признак.
_BOOTSTRAP_ADMIN_LOGIN = 'admin'


def _is_bootstrap_admin(row):
    return row['login'] == _BOOTSTRAP_ADMIN_LOGIN


def _get_user_team_ids(conn, user_id):
    return [row['team_id'] for row in conn.execute(
        'SELECT team_id FROM user_team_access WHERE user_id = ? ORDER BY team_id', (user_id,)
    ).fetchall()]


def _set_user_team_ids(conn, user_id, team_ids, role=None):
    conn.execute('DELETE FROM user_team_access WHERE user_id = ?', (user_id,))
    if role == 'admin':
        return
    for team_id in dict.fromkeys(team_ids or []):
        conn.execute('INSERT INTO user_team_access (user_id, team_id) VALUES (?, ?)', (user_id, int(team_id)))


@with_db_connection(commit_on_success=False)
def get_user_team_ids(conn, user_id):
    return _get_user_team_ids(conn, user_id)


@with_db_connection(commit_on_success=False)
def get_effective_team_ids(conn, user_id, role):
    if role == 'admin':
        return None
    team_ids = _get_user_team_ids(conn, user_id)
    return team_ids or None


@with_db_connection(commit_on_success=False)
def user_can_access_team(conn, user_id, role, team_id):
    if role == 'admin':
        return True
    restricted = conn.execute('SELECT 1 FROM user_team_access WHERE user_id = ? LIMIT 1', (user_id,)).fetchone()
    if not restricted:
        return True
    return conn.execute(
        'SELECT 1 FROM user_team_access WHERE user_id = ? AND team_id = ?', (user_id, team_id)
    ).fetchone() is not None


@with_db_connection(commit_on_success=False)
def get_task_team_id(conn, task_id):
    row = conn.execute('SELECT team_id FROM tasks WHERE id = ?', (task_id,)).fetchone()
    return row['team_id'] if row else None


@with_db_connection(commit_on_success=False)
def get_assignment_team_id(conn, assignment_id):
    row = conn.execute(
        'SELECT t.team_id FROM assignments a JOIN tasks t ON t.id = a.task_id WHERE a.id = ?',
        (assignment_id,),
    ).fetchone()
    return row['team_id'] if row else None


@with_db_connection(commit_on_success=False)
def get_team_assignees(conn, team_id):
    rows = conn.execute(
        '''SELECT u.id, u.last_name, u.first_name, u.middle_name, u.role, u.login,
                  u.is_assignee
           FROM users u
           WHERE u.is_assignee = 1 AND (
               u.role = 'admin'
               OR NOT EXISTS (SELECT 1 FROM user_team_access any_access WHERE any_access.user_id = u.id)
               OR EXISTS (SELECT 1 FROM user_team_access access
                          WHERE access.user_id = u.id AND access.team_id = ?)
           )
           ORDER BY u.last_name, u.first_name, u.middle_name''',
        (team_id,),
    ).fetchall()
    return [{**dict(row), 'is_assignee': bool(row['is_assignee'])} for row in rows]


@with_db_connection(commit_on_success=False)
def user_is_eligible_assignee(conn, user_id, team_id):
    row = conn.execute(
        '''SELECT 1 FROM users u
           WHERE u.id = ? AND u.is_assignee = 1 AND (
               u.role = 'admin'
               OR NOT EXISTS (SELECT 1 FROM user_team_access any_access WHERE any_access.user_id = u.id)
               OR EXISTS (SELECT 1 FROM user_team_access access
                          WHERE access.user_id = u.id AND access.team_id = ?)
           )''', (user_id, team_id)
    ).fetchone()
    return row is not None


@with_db_connection(commit_on_success=False)
def is_bootstrap_admin_id(conn, user_id):
    """Является ли user_id учётной записью администратора по умолчанию (см. _is_bootstrap_admin)"""
    row = conn.execute('SELECT login FROM users WHERE id = ?', (user_id,)).fetchone()
    return bool(row) and _is_bootstrap_admin(row)


@with_db_connection(commit_on_success=False)
def get_all_users(conn):
    """Получить всех пользователей"""
    users = conn.execute(
        'SELECT id, last_name, first_name, middle_name, role, login, is_assignee FROM users ORDER BY last_name, first_name, middle_name').fetchall()
    result = []
    for u in users:
        u_dict = dict(u)
        u_dict['is_assignee'] = bool(u_dict['is_assignee'])
        u_dict['is_protected'] = _is_bootstrap_admin(u)
        u_dict['team_ids'] = _get_user_team_ids(conn, u['id'])
        result.append(u_dict)
    return result


@with_db_connection(commit_on_success=False)
def get_users_page(conn, offset=0, limit=20, search=None):
    """Отфильтровать пользователей и вернуть только запрошенную страницу."""
    needle = (search or '').strip().casefold()
    searchable_text = '''
        COALESCE(login, '') || ' ' ||
        COALESCE(last_name, '') || ' ' ||
        COALESCE(first_name, '') || ' ' ||
        COALESCE(middle_name, '') || ' ' ||
        role || ' ' ||
        CASE role
            WHEN 'admin' THEN 'Администратор'
            WHEN 'editor' THEN 'Редактор'
            WHEN 'user' THEN 'Пользователь'
            ELSE ''
        END
    '''
    where_clause = f'WHERE instr(casefold({searchable_text}), ?) > 0' if needle else ''
    filter_params = (needle,) if needle else ()
    total = conn.execute(f'SELECT COUNT(*) FROM users {where_clause}', filter_params).fetchone()[0]
    page = conn.execute(
        f'''SELECT id, last_name, first_name, middle_name, role, login, is_assignee
            FROM users
            {where_clause}
            ORDER BY last_name, first_name, middle_name
            LIMIT ? OFFSET ?''',
        (*filter_params, limit, offset),
    ).fetchall()
    result = []
    for user in page:
        user_dict = dict(user)
        user_dict['is_assignee'] = bool(user_dict['is_assignee'])
        user_dict['is_protected'] = _is_bootstrap_admin(user)
        user_dict['team_ids'] = _get_user_team_ids(conn, user['id'])
        result.append(user_dict)
    return {'users': result, 'total': total}


@with_db_connection(commit_on_success=False)
def get_user(conn, user_id):
    """Получить одного пользователя по id (используется, например, GET /api/me)"""
    row = conn.execute(
        'SELECT id, last_name, first_name, middle_name, role FROM users WHERE id = ?', (user_id,)).fetchone()
    return dict(row) if row else None


@with_db_connection(default_return=None, raise_on_error=False, commit_on_success=False)
def create_user(conn, last_name, first_name, middle_name=None, password_hash=None, role='user', login=None,
                 is_assignee=True, team_ids=None):
    """Создать пользователя. Возвращает None при нарушении UNIQUE (дубль логина) —
    raise_on_error=False нужен именно для этого: без него IntegrityError улетал бы наверх
    необработанным, и вызывающий код никогда не увидел бы свою ветку "уже существует"."""
    cursor = conn.execute(
        '''INSERT INTO users (last_name, first_name, middle_name, password_hash, role, login, is_assignee)
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (last_name, first_name, middle_name, password_hash, role, login, int(is_assignee)))
    user_id = _backend.last_insert_id(cursor)
    _set_user_team_ids(conn, user_id, team_ids, role)
    return user_id


def _update_login_and_password(conn, user_id, password_hash=None, login=None):
    """Обновить только login/password_hash, не трогая ФИО/роль — используется только веткой
    бутстрап-админа в update_user (для собственного пароля пользователь пользуется отдельной
    update_own_password, которая логин не трогает вовсе)."""
    if password_hash is not None:
        conn.execute('UPDATE users SET password_hash = ? WHERE id = ?', (password_hash, user_id))
    if login is not None:
        conn.execute('UPDATE users SET login = ? WHERE id = ?', (login, user_id))


@with_db_connection(default_return=False, raise_on_error=False)
def update_own_password(conn, user_id, password_hash):
    """Пользователь меняет пароль своей же учётной записи (не через админский update_user) —
    логин, ФИО и роль этой функцией не затрагиваются: логин теперь может менять только admin."""
    conn.execute('UPDATE users SET password_hash = ? WHERE id = ?', (password_hash, user_id))
    return True


@with_db_connection(default_return=False, raise_on_error=False)
def update_user(conn, user_id, last_name, first_name, middle_name=None, password_hash=None, role='user', login=None,
                 is_assignee=True, team_ids=None):
    """Обновить пользователя. password_hash=None означает "не менять пароль", login=None — "не менять логин".
    Для учётной записи администратора по умолчанию ФИО и роль никогда не перезаписываются этой
    функцией (можно поменять только пароль и логин) — независимо от того, что пришло в
    last_name/first_name/middle_name/role, чтобы не зависеть от того, отправил ли клиент эти поля вообще."""
    current = conn.execute('SELECT login FROM users WHERE id = ?', (user_id,)).fetchone()
    if not current:
        return False

    if _is_bootstrap_admin(current):
        _update_login_and_password(conn, user_id, password_hash, login)
        _set_user_team_ids(conn, user_id, [], 'admin')
        return True

    if password_hash is not None:
        conn.execute(
            '''UPDATE users
               SET last_name     = ?,
                   first_name    = ?,
                   middle_name   = ?,
                   password_hash = ?,
                   role          = ?,
                   login         = ?,
                   is_assignee   = ?
               WHERE id = ?''',
            (last_name, first_name, middle_name, password_hash, role, login, int(is_assignee), user_id))
    else:
        conn.execute(
            '''UPDATE users
               SET last_name   = ?,
                   first_name  = ?,
                   middle_name = ?,
                   role        = ?,
                   login       = ?,
                   is_assignee = ?
               WHERE id = ?''', (last_name, first_name, middle_name, role, login, int(is_assignee), user_id))
    _set_user_team_ids(conn, user_id, team_ids, role)
    return True


@with_db_connection(commit_on_success=False)
def get_user_auth_by_login(conn, login):
    """Получить id, хэш пароля и роль пользователя по логину — для проверки при входе"""
    row = conn.execute('SELECT id, password_hash, role FROM users WHERE login = ?', (login,)).fetchone()
    return dict(row) if row else None


@with_db_connection()
def delete_user(conn, user_id, changed_by=None):
    """Удалить пользователя"""
    user = conn.execute('SELECT login FROM users WHERE id = ?', (user_id,)).fetchone()
    if user and _is_bootstrap_admin(user):
        raise ValueError('Нельзя удалить учётную запись администратора по умолчанию')

    affected = conn.execute(
        'SELECT id, task_id, date, user_id FROM assignments WHERE user_id = ?', (user_id,)
    ).fetchall()
    if affected:
        conn.execute('UPDATE assignments SET user_id = NULL WHERE user_id = ?', (user_id,))
        for row in affected:
            _record_assignment_history(
                conn, row['id'], row['task_id'], row['date'], 'update',
                field_name='user_id', old_value=str(row['user_id']), new_value=None,
                changed_by=changed_by)
    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))


# === FREEZE DAYS CRUD ===
@with_db_connection(commit_on_success=False)
def get_all_freeze_days(conn):
    """Получить все дни фриза"""
    days = conn.execute('SELECT date FROM freeze_days ORDER BY date').fetchall()
    return [day['date'] for day in days]


@with_db_connection(commit_on_success=False)
def get_freeze_days_in_period(conn, start_date, end_date):
    """Получить дни фриза в заданном периоде"""
    days = conn.execute(
        'SELECT date FROM freeze_days WHERE date BETWEEN ? AND ? ORDER BY date',
        (start_date, end_date)
    ).fetchall()
    return [day['date'] for day in days]


@with_db_connection(default_return=False, raise_on_error=False)
def add_freeze_day(conn, date_str):
    """Добавить день фриза"""
    conn.execute('INSERT INTO freeze_days (date) VALUES (?)', (date_str,))
    return True


@with_db_connection()
def add_freeze_range(conn, start_date, end_date):
    """Добавить диапазон дней фриза"""
    start = datetime.strptime(start_date, '%Y-%m-%d').date()
    end = datetime.strptime(end_date, '%Y-%m-%d').date()

    added = 0
    current = start
    while current <= end:
        date_str = current.strftime('%Y-%m-%d')
        try:
            conn.execute('INSERT INTO freeze_days (date) VALUES (?)', (date_str,))
            added += 1
        except _backend.duplicate_error:
            pass
        current += timedelta(days=1)
    return added


@with_db_connection()
def remove_freeze_day(conn, date_str):
    """Удалить день фриза"""
    conn.execute('DELETE FROM freeze_days WHERE date = ?', (date_str,))


@with_db_connection()
def delete_freeze_days_by_month(conn, year, month):
    prefix = f"{year}-{month:02d}-%"
    conn.execute("DELETE FROM freeze_days WHERE date LIKE ?", (prefix,))


@with_db_connection()
def set_freeze_days_for_month(conn, year, month, days):
    prefix = f"{year}-{month:02d}-%"
    conn.execute("DELETE FROM freeze_days WHERE date LIKE ?", (prefix,))
    for day in days:
        date_str = f"{year}-{month:02d}-{day:02d}"
        conn.execute("INSERT OR IGNORE INTO freeze_days (date) VALUES (?)", (date_str,))


# === TASKS CRUD ===
def _fuzzy_search_clause(search, name_col='name', description_col='description'):
    """Строит WHERE-фрагмент и параметры для нечёткого поиска задач по словам: каждое слово
    должно совпасть (через fuzzy_word_in) с name ИЛИ description. Пустой search -> ("", []).
    name_col/description_col позволяют квалифицировать колонки при JOIN (см. get_tasks_by_team)."""
    if not search:
        return "", []
    words = search.split()
    word_clauses = " AND ".join(
        f"(fuzzy_word_in({name_col}, ?) OR fuzzy_word_in({description_col}, ?))" for _ in words
    )
    params = []
    for word in words:
        params += [word, word]
    return f"AND ({word_clauses})", params


@with_db_connection(commit_on_success=False)
def get_tasks_by_team(conn, team_id, offset=0, limit=10, search=None, include_recent_completed=False):
    """Получить задачи команды с пагинацией и поиском"""
    completed_clause = (
        "AND (tasks.task_status NOT IN ('done', 'cancelled') OR "
        "(tasks.completed_at IS NOT NULL AND tasks.completed_at >= datetime('now', '-30 days')))"
        if include_recent_completed else "AND tasks.task_status NOT IN ('done', 'cancelled')"
    )
    params = [team_id]
    search_clause, search_params = _fuzzy_search_clause(search, 'tasks.name', 'tasks.description')
    params += search_params
    params += [limit, offset]
    # @formatter:off
    return conn.execute(
        f'''SELECT tasks.id, tasks.name, tasks.description, tasks.criticality, tasks.task_status,
                   tasks.segment_id, segments.name AS segment_name, tasks.completed_at,
                   EXISTS(SELECT 1 FROM assignments a WHERE a.task_id = tasks.id AND a.is_deleted = 0
                          AND a.status != 'new') AS has_active_assignments
            FROM tasks
            JOIN segments ON tasks.segment_id = segments.id
            WHERE tasks.team_id = ?
              AND tasks.is_deleted = 0
            {completed_clause}
            {search_clause}
            ORDER BY CASE tasks.criticality
                         WHEN 'high'   THEN 0
                         WHEN 'medium' THEN 1
                         WHEN 'low'    THEN 2
                         ELSE 3
                         END,
                     tasks.priority DESC, tasks.id
            LIMIT ? OFFSET ?''',
        params
    ).fetchall()
    # @formatter:on


@with_db_connection(commit_on_success=False)
def get_tasks_count_by_team(conn, team_id, search=None, include_recent_completed=False):
    """Получить общее количество задач команды (с учётом поиска)"""
    completed_clause = (
        "AND (task_status NOT IN ('done', 'cancelled') OR "
        "(completed_at IS NOT NULL AND completed_at >= datetime('now', '-30 days')))"
        if include_recent_completed else "AND task_status NOT IN ('done', 'cancelled')"
    )
    params = [team_id]
    search_clause, search_params = _fuzzy_search_clause(search)
    params += search_params
    return conn.execute(
        f"SELECT COUNT(*) FROM tasks WHERE team_id = ? AND is_deleted = 0 {completed_clause} {search_clause}",
        params
    ).fetchone()[0]


@with_db_connection(commit_on_success=False)
def get_task_by_id(conn, task_id):
    return conn.execute(
        '''SELECT tasks.id, tasks.team_id, tasks.name, tasks.description, tasks.criticality,
                  tasks.task_status, tasks.segment_id, segments.name AS segment_name,
                  tasks.completed_at,
                  EXISTS(SELECT 1 FROM assignments a WHERE a.task_id = tasks.id AND a.is_deleted = 0
                         AND a.status != 'new') AS has_active_assignments
             FROM tasks JOIN segments ON tasks.segment_id = segments.id
            WHERE tasks.id = ? AND tasks.is_deleted = 0''',
        (task_id,),
    ).fetchone()


def _archive_filter(search, completed_from, completed_to):
    clauses = ["tasks.task_status IN ('done', 'cancelled')"]
    params = []
    search_clause, search_params = _fuzzy_search_clause(search, 'tasks.name', 'tasks.description')
    if search_clause:
        clauses.append(search_clause.removeprefix('AND '))
        params.extend(search_params)
    if completed_from:
        clauses.append("tasks.completed_at >= ? || ' 00:00:00'")
        params.append(completed_from)
    if completed_to:
        clauses.append("tasks.completed_at < datetime(?, '+1 day')")
        params.append(completed_to)
    return ' AND '.join(clauses), params


@with_db_connection(commit_on_success=False)
def get_archived_tasks_by_team(conn, team_id, offset=0, limit=20, search=None,
                               completed_from=None, completed_to=None):
    filters, filter_params = _archive_filter(search, completed_from, completed_to)
    return conn.execute(
        f'''SELECT tasks.id, tasks.name, tasks.description, tasks.criticality, tasks.task_status,
                   tasks.segment_id, segments.name AS segment_name, tasks.completed_at,
                   EXISTS(SELECT 1 FROM assignments a WHERE a.task_id = tasks.id AND a.is_deleted = 0
                          AND a.status != 'new') AS has_active_assignments
              FROM tasks JOIN segments ON tasks.segment_id = segments.id
             WHERE tasks.team_id = ? AND tasks.is_deleted = 0 AND {filters}
             ORDER BY tasks.completed_at IS NULL, tasks.completed_at DESC, tasks.id DESC
             LIMIT ? OFFSET ?''',
        [team_id, *filter_params, limit, offset],
    ).fetchall()


@with_db_connection(commit_on_success=False)
def get_archived_tasks_count_by_team(conn, team_id, search=None, completed_from=None, completed_to=None):
    filters, filter_params = _archive_filter(search, completed_from, completed_to)
    return conn.execute(
        f'''SELECT COUNT(*) FROM tasks
             WHERE team_id = ? AND is_deleted = 0 AND {filters.replace('tasks.', '')}''',
        [team_id, *filter_params],
    ).fetchone()[0]


def _priority_at_tier_end(conn, team_id, criticality, exclude_task_id=None):
    """Значение priority, ставящее задачу в конец (наименее приоритетной позиции) её пары
    (team_id, criticality) — используется и при создании задачи, и при переносе существующей
    задачи в другой уровень критичности."""
    exclude_clause = 'AND id != ?' if exclude_task_id is not None else ''
    params = [team_id, criticality] + ([exclude_task_id] if exclude_task_id is not None else [])
    min_priority = conn.execute(
        f'SELECT MIN(priority) FROM tasks WHERE team_id = ? AND criticality = ? AND is_deleted = 0 {exclude_clause}',
        params
    ).fetchone()[0]
    return (min_priority - _PRIORITY_GAP) if min_priority is not None else 0


def _record_task_history(conn, task_id, action, field_name=None, old_value=None, new_value=None, changed_by=None):
    conn.execute(
        '''INSERT INTO task_history (task_id, action, field_name, old_value, new_value, changed_by_user_id)
           VALUES (?, ?, ?, ?, ?, ?)''',
        (task_id, action, field_name, old_value, new_value, changed_by))


def _record_assignment_history(conn, assignment_id, task_id, date_str, action, field_name=None, old_value=None,
                                new_value=None, changed_by=None):
    conn.execute(
        '''INSERT INTO assignment_history
               (assignment_id, task_id, date, action, field_name, old_value, new_value, changed_by_user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (assignment_id, task_id, date_str, action, field_name, old_value, new_value, changed_by))


@with_db_connection(commit_on_success=False)
def task_exists(conn, task_id):
    """Проверить существование (неудалённой) задачи"""
    return conn.execute('SELECT 1 FROM tasks WHERE id = ? AND is_deleted = 0', (task_id,)).fetchone()


@with_db_connection(commit_on_success=False)
def task_has_active_assignments(conn, task_id):
    """Есть ли у задачи (неудалённые) назначения со статусом, отличным от 'new'"""
    row = conn.execute(
        "SELECT 1 FROM assignments WHERE task_id = ? AND is_deleted = 0 AND status != 'new' LIMIT 1",
        (task_id,)
    ).fetchone()
    return row is not None


@with_db_connection()
def create_or_update_task(conn, task_id, team_id, name, description, criticality='medium', segment_id=None,
                           changed_by=None):
    """Создать или обновить задачу. priority этой функцией напрямую не редактируется — им
    управляют reorder_team_tasks/move_task_to_edge — за исключением одного случая: если на UPDATE
    меняется criticality, задача пересчитывается в конец списка НОВОГО уровня критичности (как
    новая задача), т.к. её старое числовое значение priority больше ничего не значит относительно
    задач другого уровня. На CREATE новая задача всегда уходит в конец списка своего уровня
    критичности (наименьший приоритет внутри него)."""
    existing = conn.execute('SELECT name, description, criticality, priority, segment_id FROM tasks WHERE id = ?',
                             (task_id,)).fetchone()
    if existing:
        for field, new_val in (('name', name), ('description', description), ('criticality', criticality),
                                ('segment_id', segment_id)):
            old_val = existing[field]
            if old_val != new_val:
                _record_task_history(conn, task_id, 'update', field_name=field,
                                      old_value=old_val, new_value=new_val, changed_by=changed_by)
        new_priority = existing['priority']
        if criticality != existing['criticality']:
            new_priority = _priority_at_tier_end(conn, team_id, criticality, exclude_task_id=task_id)
            if new_priority != existing['priority']:
                _record_task_history(conn, task_id, 'update', field_name='priority',
                                      old_value=str(existing['priority']), new_value=str(new_priority),
                                      changed_by=changed_by)
        conn.execute(
            '''UPDATE tasks
               SET name        = ?,
                   description = ?,
                   criticality = ?,
                   segment_id  = ?,
                   priority    = ?
               WHERE id = ?''',
            (name, description, criticality, segment_id, new_priority, task_id)
        )
    else:
        new_priority = _priority_at_tier_end(conn, team_id, criticality)
        cursor = conn.execute(
            'INSERT INTO tasks (team_id, name, description, criticality, segment_id, priority) '
            'VALUES (?, ?, ?, ?, ?, ?)',
            (team_id, name, description, criticality, segment_id, new_priority)
        )
        task_id = _backend.last_insert_id(cursor)
        snapshot = json.dumps({'team_id': team_id, 'name': name, 'description': description,
                                'criticality': criticality, 'segment_id': segment_id, 'priority': new_priority},
                               ensure_ascii=False)
        _record_task_history(conn, task_id, 'create', new_value=snapshot, changed_by=changed_by)
    return task_id


@with_db_connection()
def reorder_team_tasks(conn, team_id, task_ids, changed_by=None):
    """Переупорядочить задачи в пределах уже загруженной страницы (drag-and-drop).

    task_ids — новый порядок ровно тех задач, что были на странице, от самой важной к наименее
    важной. Алгоритм не создаёт новых значений priority и никогда не "выходит" за диапазон
    страницы: берёт ТЕКУЩИЕ priority ровно этого набора задач, сортирует их по убыванию и
    раздаёт заново в новом порядке — первая задача нового порядка получает наибольшее из уже
    существующих значений, и т.д. Только реально изменившиеся строки попадают в историю.

    Все task_ids должны принадлежать одному уровню критичности — приоритет можно менять только
    внутри уровня, не поперёк него (граница обеспечивается и на фронтенде, но здесь — источник
    истины). Ни одна из задач не должна быть в терминальном статусе (done/cancelled) — приоритет
    завершённой/отменённой работы больше не имеет смысла менять."""
    if len(task_ids) != len(set(task_ids)):
        raise ValueError('Дублирующиеся task_id')
    if not task_ids:
        return True

    placeholders = ','.join('?' * len(task_ids))
    rows = conn.execute(
        f'''SELECT id, priority, criticality, task_status FROM tasks
            WHERE id IN ({placeholders}) AND team_id = ? AND is_deleted = 0''',
        (*task_ids, team_id)
    ).fetchall()
    priority_by_id = {r['id']: r['priority'] for r in rows}
    if set(priority_by_id) != set(task_ids):
        raise ValueError('Некоторые задачи не найдены в этой команде или удалены')
    if len({r['criticality'] for r in rows}) > 1:
        raise ValueError('Приоритет можно менять только в пределах одного уровня критичности')
    if any(r['task_status'] in ('done', 'cancelled') for r in rows):
        raise ValueError('Нельзя менять приоритет завершённой или отменённой задачи')

    priorities_desc = sorted(priority_by_id.values(), reverse=True)
    for tid, new_priority in zip(task_ids, priorities_desc):
        old_priority = priority_by_id[tid]
        if old_priority == new_priority:
            continue
        _record_task_history(conn, tid, 'update', field_name='priority',
                              old_value=str(old_priority), new_value=str(new_priority), changed_by=changed_by)
        conn.execute('UPDATE tasks SET priority = ? WHERE id = ?', (new_priority, tid))
    return True


@with_db_connection()
def move_task_to_edge(conn, task_id, position, changed_by=None):
    """Переместить задачу в начало (position='start') или конец ('end') списка её уровня
    критичности внутри её команды (контекстное меню). team_id намеренно не принимается параметром —
    команда (и уровень критичности) определяются самой задачей, так что подделать их через
    фронтенд нельзя."""
    task = conn.execute('SELECT priority, team_id, criticality, task_status, is_deleted FROM tasks WHERE id = ?',
                         (task_id,)).fetchone()
    if not task or task['is_deleted']:
        raise ValueError('Задача не найдена')
    if task['task_status'] in ('done', 'cancelled'):
        raise ValueError('Нельзя менять приоритет завершённой или отменённой задачи')

    agg_col = 'MAX(priority)' if position == 'start' else 'MIN(priority)'
    edge_row = conn.execute(
        f'SELECT {agg_col} AS edge FROM tasks WHERE team_id = ? AND criticality = ? AND is_deleted = 0 AND id != ?',
        (task['team_id'], task['criticality'], task_id)
    ).fetchone()
    edge = edge_row['edge']
    old_priority = task['priority']

    if edge is None:
        return True  # единственная задача команды — двигать некуда

    already_there = old_priority >= edge if position == 'start' else old_priority <= edge
    if already_there:
        return True  # уже на нужном краю — no-op

    new_priority = edge + _PRIORITY_GAP if position == 'start' else edge - _PRIORITY_GAP
    _record_task_history(conn, task_id, 'update', field_name='priority',
                          old_value=str(old_priority), new_value=str(new_priority), changed_by=changed_by)
    conn.execute('UPDATE tasks SET priority = ? WHERE id = ?', (new_priority, task_id))
    return True


@with_db_connection()
def delete_task(conn, task_id, changed_by=None):
    """Мягко удалить задачу (is_deleted=1, без физического DELETE) вместе со всеми её назначениями"""
    task = conn.execute('SELECT is_deleted FROM tasks WHERE id = ?', (task_id,)).fetchone()
    if not task or task['is_deleted']:
        return  # не существует или уже удалена — идемпотентно
    _record_task_history(conn, task_id, 'update', field_name='is_deleted',
                          old_value='0', new_value='1', changed_by=changed_by)
    conn.execute('UPDATE tasks SET is_deleted = 1 WHERE id = ?', (task_id,))
    assignments = conn.execute(
        'SELECT id, date FROM assignments WHERE task_id = ? AND is_deleted = 0', (task_id,)
    ).fetchall()
    for a in assignments:
        _record_assignment_history(conn, a['id'], task_id, a['date'], 'update', field_name='is_deleted',
                                    old_value='0', new_value='1', changed_by=changed_by)
    conn.execute('UPDATE assignments SET is_deleted = 1 WHERE task_id = ? AND is_deleted = 0', (task_id,))


@with_db_connection(commit_on_success=False)
def get_task_status(conn, task_id):
    """Получить текущий статус задачи и признак удаления"""
    return conn.execute('SELECT task_status, is_deleted FROM tasks WHERE id = ?', (task_id,)).fetchone()


@with_db_connection(commit_on_success=False)
def get_task_status_by_assignment(conn, assignment_id):
    """Получить статус задачи, признак её удаления и статус самого назначения по ID назначения"""
    return conn.execute(
        'SELECT t.task_status, t.is_deleted, a.status AS assignment_status '
        'FROM assignments a JOIN tasks t ON a.task_id = t.id WHERE a.id = ?',
        (assignment_id,)
    ).fetchone()


@with_db_connection()
def update_task_status(conn, task_id, new_status, changed_by=None):
    """Обновить статус задачи"""
    current = conn.execute("SELECT task_status FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if current and current['task_status'] != new_status:
        _record_task_history(conn, task_id, 'update', field_name='task_status',
                              old_value=current['task_status'], new_value=new_status, changed_by=changed_by)
    old_status = current['task_status'] if current else None
    old_terminal = old_status in ('done', 'cancelled')
    new_terminal = new_status in ('done', 'cancelled')
    if new_terminal and not old_terminal:
        conn.execute("UPDATE tasks SET task_status = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?",
                     (new_status, task_id))
    elif old_terminal and not new_terminal:
        conn.execute("UPDATE tasks SET task_status = ?, completed_at = NULL WHERE id = ?", (new_status, task_id))
    else:
        conn.execute("UPDATE tasks SET task_status = ? WHERE id = ?", (new_status, task_id))
    return True


@with_db_connection()
def restore_task(conn, task_id, changed_by=None):
    """Restore a terminal task without changing its related entities."""
    current = conn.execute(
        'SELECT task_status, is_deleted FROM tasks WHERE id = ?', (task_id,)
    ).fetchone()
    if not current or current['is_deleted']:
        return False
    if current['task_status'] not in ('done', 'cancelled'):
        raise ValueError('Восстановить можно только завершённую или отменённую работу')
    _record_task_history(conn, task_id, 'update', field_name='task_status',
                         old_value=current['task_status'], new_value='new', changed_by=changed_by)
    conn.execute(
        "UPDATE tasks SET task_status = 'new', completed_at = NULL WHERE id = ?",
        (task_id,),
    )
    return True


# === TASK DEPENDENCIES ===

@with_db_connection(commit_on_success=False)
def get_all_deps_for_team(conn, team_id, task_ids=None):
    """Получить зависимости задач команды (опционально ограниченные списком task_ids)"""
    if task_ids is not None and len(task_ids) == 0:
        return []
    # @formatter:off
    query = '''SELECT td.task_id, td.depends_on_task_id AS dep_id,
                      dep.name AS dep_name, dep.task_status AS dep_status, dep.is_deleted AS dep_is_deleted,
                      dep.criticality AS dep_criticality, dep.segment_id AS dep_segment_id,
                      seg.name AS dep_segment_name
               FROM task_dependencies td
               JOIN tasks src ON td.task_id            = src.id
               JOIN tasks dep ON td.depends_on_task_id = dep.id
               JOIN segments seg ON dep.segment_id     = seg.id
               WHERE src.team_id = ?'''
    # @formatter:on
    params = [team_id]
    if task_ids:
        placeholders = ','.join('?' * len(task_ids))
        query += f' AND td.task_id IN ({placeholders})'
        params.extend(task_ids)
    return conn.execute(query, tuple(params)).fetchall()


@with_db_connection()
def set_task_dependencies(conn, task_id, dep_ids):
    conn.execute('DELETE FROM task_dependencies WHERE task_id = ?', (task_id,))
    for dep_id in dep_ids:
        _add_task_dependency(conn, task_id, dep_id)


def _add_task_dependency(conn, task_id, depends_on_task_id):
    conn.execute(
        'INSERT OR IGNORE INTO task_dependencies (task_id, depends_on_task_id) VALUES (?, ?)',
        (task_id, depends_on_task_id)
    )


@with_db_connection()
def add_task_dependency(conn, task_id, depends_on_task_id):
    _add_task_dependency(conn, task_id, depends_on_task_id)


@with_db_connection()
def remove_task_dependency(conn, task_id, depends_on_task_id):
    conn.execute(
        'DELETE FROM task_dependencies WHERE task_id = ? AND depends_on_task_id = ?',
        (task_id, depends_on_task_id)
    )


@with_db_connection(commit_on_success=False)
def get_tasks_for_dependency_edit(conn, task_id, depends_on_task_id):
    """Загружает team_id/task_status/is_deleted обеих задач одним запросом — используется
    эндпоинтами добавления/удаления одной связи, чтобы проверить принадлежность одной команде
    и терминальный статус зависящей задачи перед мутацией."""
    rows = conn.execute(
        'SELECT id, team_id, task_status, is_deleted FROM tasks WHERE id IN (?, ?)',
        (task_id, depends_on_task_id)
    ).fetchall()
    by_id = {r['id']: r for r in rows}
    return by_id.get(task_id), by_id.get(depends_on_task_id)


@with_db_connection(commit_on_success=False)
def has_dependency_cycle(conn, task_id, new_dep_ids):
    """BFS: достижим ли task_id из new_dep_ids по существующим рёбрам зависимостей?
    Если да — добавление этих зависимостей создаст цикл."""
    visited = set()
    queue = list(new_dep_ids)
    while queue:
        current = queue.pop()
        if current == task_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        rows = conn.execute(
            'SELECT depends_on_task_id FROM task_dependencies WHERE task_id = ?',
            (current,)
        ).fetchall()
        queue.extend(r['depends_on_task_id'] for r in rows)
    return False


def _dependency_component_ids(conn, task_id):
    """BFS в обе стороны по task_dependencies от task_id: предки (от кого зависит task_id,
    через depends_on_task_id) и потомки (кто зависит от task_id, через task_id) — тот же
    итеративный BFS, что и has_dependency_cycle, только собирающий посещённые id вместо
    проверки достижимости."""
    visited = {task_id}
    queue = [task_id]
    while queue:
        current = queue.pop()
        ancestor_rows = conn.execute(
            'SELECT depends_on_task_id FROM task_dependencies WHERE task_id = ?', (current,)
        ).fetchall()
        descendant_rows = conn.execute(
            'SELECT task_id FROM task_dependencies WHERE depends_on_task_id = ?', (current,)
        ).fetchall()
        for row in ancestor_rows:
            neighbor = row['depends_on_task_id']
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
        for row in descendant_rows:
            neighbor = row['task_id']
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    return visited


@with_db_connection(commit_on_success=False)
def get_dependency_graph_for_team(conn, team_id, task_id=None):
    """Граф зависимостей для визуализации — в отличие от get_all_deps_for_team не ограничен
    списком уже загруженных task_ids.

    Без task_id: все не удалённые задачи команды, состоящие хотя бы в одной видимой связи
    (изолированные задачи без единой зависимости исключаются, чтобы общий граф команды не
    превращался в "паутину" из несвязанных узлов).

    С task_id: только связная компонента конкретной задачи (её предки и потомки по цепочке
    зависимостей в обе стороны) — сама задача включается всегда, даже если у неё нет ни одной
    связи.

    В обоих случаях связь между двумя задачами, уже находящимися в терминальном статусе
    (done/cancelled), не возвращается — обе стороны завершены, и такая связь не несёт полезной
    информации для текущего планирования."""
    # @formatter:off
    terminal_edge_filter = "NOT (src.task_status IN ('done', 'cancelled') AND dep.task_status IN ('done', 'cancelled'))"
    if task_id is not None:
        component_ids = _dependency_component_ids(conn, task_id)
        placeholders = ','.join('?' * len(component_ids))
        params = tuple(component_ids)
        nodes = conn.execute(
            f'''SELECT t.id, t.name, t.description, t.task_status, t.criticality,
                       t.segment_id, seg.name AS segment_name
                FROM tasks t
                JOIN segments seg ON t.segment_id = seg.id
                WHERE t.team_id = ? AND t.is_deleted = 0 AND t.id IN ({placeholders})''',
            (team_id, *params)
        ).fetchall()
        edges = conn.execute(
            f'''SELECT td.task_id, td.depends_on_task_id AS dep_id
                FROM task_dependencies td
                JOIN tasks src ON td.task_id            = src.id
                JOIN tasks dep ON td.depends_on_task_id = dep.id
                WHERE src.team_id = ? AND src.is_deleted = 0 AND dep.is_deleted = 0
                  AND td.task_id IN ({placeholders}) AND td.depends_on_task_id IN ({placeholders})
                  AND {terminal_edge_filter}''',
            (team_id, *params, *params)
        ).fetchall()
    else:
        edges = conn.execute(
            f'''SELECT td.task_id, td.depends_on_task_id AS dep_id
                FROM task_dependencies td
                JOIN tasks src ON td.task_id            = src.id
                JOIN tasks dep ON td.depends_on_task_id = dep.id
                WHERE src.team_id = ? AND src.is_deleted = 0 AND dep.is_deleted = 0
                  AND {terminal_edge_filter}''',
            (team_id,)
        ).fetchall()
        node_ids = {e['task_id'] for e in edges} | {e['dep_id'] for e in edges}
        placeholders = ','.join('?' * len(node_ids)) if node_ids else 'NULL'
        nodes = conn.execute(
            f'''SELECT t.id, t.name, t.description, t.task_status, t.criticality,
                      t.segment_id, seg.name AS segment_name
               FROM tasks t
               JOIN segments seg ON t.segment_id = seg.id
               WHERE t.team_id = ? AND t.is_deleted = 0 AND t.id IN ({placeholders})''',
            (team_id, *node_ids)
        ).fetchall() if node_ids else []
    # @formatter:on
    return {'nodes': nodes, 'edges': edges}


@with_db_connection(commit_on_success=False)
def get_active_tasks_flat(conn, team_id, search=None, limit=50, include_ids=None):
    params = [team_id]
    search_clause, search_params = _fuzzy_search_clause(search)
    params += search_params
    params.append(limit)

    include_clause = ""
    if include_ids:
        placeholders = ','.join('?' * len(include_ids))
        include_clause = f'''
            UNION
            SELECT id, name, task_status, criticality
            FROM tasks
            WHERE team_id = ? AND is_deleted = 0 AND id IN ({placeholders})
        '''
        params.append(team_id)
        params += list(include_ids)

    # @formatter:off
    query = f'''
        SELECT id, name, task_status, criticality FROM (
            SELECT id, name, task_status, criticality
            FROM tasks
            WHERE team_id = ?
              AND is_deleted = 0
              AND task_status NOT IN ('done', 'cancelled')
              {search_clause}
            ORDER BY name
            LIMIT ?
        )
        {include_clause}
        ORDER BY name
    '''
    # @formatter:on
    return conn.execute(query, params).fetchall()


# === ASSIGNMENTS CRUD ===
@with_db_connection(commit_on_success=False)
def get_assignment(conn, task_id, date_str):
    """Получить назначение на задачу на конкретную дату"""
    return conn.execute(
        '''SELECT a.id,
                  a.task_id,
                  a.date,
                  a.block,
                  a.status,
                  a.user_id,
                  a.comment,
                  a.time_spent,
                  u.last_name   as user_last_name,
                  u.first_name  as user_first_name,
                  u.middle_name as user_middle_name
           FROM assignments a
                    LEFT JOIN users u ON a.user_id = u.id
           WHERE a.task_id = ?
             AND a.date = ?
             AND a.is_deleted = 0''',
        (task_id, date_str)
    ).fetchone()


@with_db_connection(commit_on_success=False)
def get_assignments_by_team_in_period(conn, team_id, start_date, end_date, task_ids=None):
    """Получить все назначения команды в период (опционально ограниченные списком task_ids)"""
    if task_ids is not None and len(task_ids) == 0:
        return []
    # @formatter:off
    query = '''SELECT a.id,
                      a.task_id,
                      a.date,
                      a.block,
                      a.status,
                      a.user_id,
                      a.comment,
                      a.time_spent,
                      u.last_name   as user_last_name,
                      u.first_name  as user_first_name,
                      u.middle_name as user_middle_name
               FROM assignments a
                        JOIN tasks t ON a.task_id = t.id
                        LEFT JOIN users u ON a.user_id = u.id
               WHERE t.team_id = ?
                 AND a.is_deleted = 0
                 AND a.date BETWEEN ? AND ?'''
    # @formatter:on
    params = [team_id, start_date, end_date]
    if task_ids:
        placeholders = ','.join('?' * len(task_ids))
        query += f' AND a.task_id IN ({placeholders})'
        params.extend(task_ids)
    query += ' ORDER BY a.date, t.id'
    return conn.execute(query, tuple(params)).fetchall()


@with_db_connection()
def create_or_update_assignment(conn, assignment_id, task_id, date_str, block, status, user_id, comment,
                                 time_spent=None, changed_by=None):
    """Создать или обновить назначение"""
    existing = conn.execute('SELECT * FROM assignments WHERE id = ?', (assignment_id,)).fetchone()

    new_values = {'date': date_str, 'task_id': task_id, 'block': block, 'status': status,
                  'user_id': user_id, 'comment': comment, 'time_spent': time_spent}

    if existing:
        for field, new_val in new_values.items():
            old_val = existing[field]
            if old_val != new_val:
                _record_assignment_history(conn, assignment_id, task_id, date_str, 'update', field_name=field,
                                            old_value=old_val, new_value=new_val, changed_by=changed_by)
        conn.execute(
            '''UPDATE assignments
               SET date        = ?,
                   task_id     = ?,
                   block       = ?,
                   status      = ?,
                   user_id     = ?,
                   comment     = ?,
                   time_spent  = ?
               WHERE id = ?''',
            (date_str, task_id, block, status, user_id, comment, time_spent, assignment_id)
        )
    else:
        cursor = conn.execute(
            '''INSERT INTO assignments (task_id, date, block, status, user_id, comment, time_spent)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (task_id, date_str, block, status, user_id, comment, time_spent)
        )
        new_assignment_id = _backend.last_insert_id(cursor)
        snapshot = json.dumps(new_values, ensure_ascii=False, default=str)
        _record_assignment_history(conn, new_assignment_id, task_id, date_str, 'create',
                                    new_value=snapshot, changed_by=changed_by)


@with_db_connection()
def bulk_reschedule_assignments(conn, moves, role, changed_by=None):
    """Атомарно перенести назначения на новые даты с проверкой итоговой раскладки."""
    if not moves:
        raise BulkAssignmentRescheduleError('Не выбраны назначения для переноса')
    if len(moves) > 200:
        raise BulkAssignmentRescheduleError('За один раз можно перенести не более 200 назначений')

    assignment_ids = [move['assignment_id'] for move in moves]
    if len(set(assignment_ids)) != len(assignment_ids):
        raise BulkAssignmentRescheduleError('Список содержит повторяющиеся назначения')

    placeholders = ','.join('?' * len(assignment_ids))
    rows = conn.execute(
        f'''SELECT a.id, a.task_id, a.date, a.status, a.is_deleted, t.task_status, t.is_deleted AS task_is_deleted
            FROM assignments a
            JOIN tasks t ON t.id = a.task_id
            WHERE a.id IN ({placeholders})''',
        assignment_ids
    ).fetchall()
    rows_by_id = {row['id']: row for row in rows}
    if len(rows_by_id) != len(assignment_ids) or any(
            rows_by_id[assignment_id]['is_deleted'] or rows_by_id[assignment_id]['task_is_deleted']
            for assignment_id in assignment_ids if assignment_id in rows_by_id):
        raise BulkAssignmentRescheduleError('Одно или несколько назначений не найдены', status_code=404)

    final_keys = set()
    normalized_moves = []
    for move in moves:
        row = rows_by_id[move['assignment_id']]
        if row['task_status'] in ('done', 'cancelled'):
            raise BulkAssignmentRescheduleError(
                'Нельзя изменять назначения завершённой или отменённой задачи')
        if role == 'user' and row['status'] != 'new':
            raise BulkAssignmentRescheduleError(
                'Недостаточно прав: нельзя изменять назначение в статусе, отличном от «Новый»',
                status_code=403)

        new_date = move['new_date']
        try:
            parsed_date = datetime.strptime(new_date, '%Y-%m-%d')
        except (TypeError, ValueError):
            raise BulkAssignmentRescheduleError('Дата переноса должна быть в формате ГГГГ-ММ-ДД')
        if not 2000 <= parsed_date.year <= 2099:
            raise BulkAssignmentRescheduleError('Дата переноса должна быть в диапазоне 2000–2099 годов')

        final_key = (row['task_id'], new_date)
        if final_key in final_keys:
            raise BulkAssignmentRescheduleError('Несколько назначений попадают в одну ячейку')
        final_keys.add(final_key)
        normalized_moves.append((row, new_date))

    for task_id, new_date in final_keys:
        occupant = conn.execute(
            '''SELECT id FROM assignments
               WHERE task_id = ? AND date = ? AND is_deleted = 0''',
            (task_id, new_date)
        ).fetchone()
        if occupant and occupant['id'] not in rows_by_id:
            raise BulkAssignmentRescheduleError('Одна из целевых ячеек уже занята')

    changed_moves = [(row, new_date) for row, new_date in normalized_moves if row['date'] != new_date]
    operation_token = uuid.uuid4().hex
    for row, _new_date in changed_moves:
        staged_date = f'__bulk_reschedule__{operation_token}_{row["id"]}'
        conn.execute('UPDATE assignments SET date = ? WHERE id = ?', (staged_date, row['id']))

    for row, new_date in changed_moves:
        conn.execute('UPDATE assignments SET date = ? WHERE id = ?', (new_date, row['id']))
        _record_assignment_history(
            conn, row['id'], row['task_id'], new_date, 'update', field_name='date',
            old_value=row['date'], new_value=new_date, changed_by=changed_by
        )

    return len(changed_moves)


@with_db_connection()
def delete_assignment(conn, assignment_id, changed_by=None):
    """Мягко удалить назначение (is_deleted=1, без физического DELETE)"""
    row = conn.execute(
        'SELECT task_id, date, is_deleted FROM assignments WHERE id = ?', (assignment_id,)
    ).fetchone()
    if not row or row['is_deleted']:
        return  # не существует или уже удалено — идемпотентно
    _record_assignment_history(conn, assignment_id, row['task_id'], row['date'], 'update', field_name='is_deleted',
                                old_value='0', new_value='1', changed_by=changed_by)
    conn.execute('UPDATE assignments SET is_deleted = 1 WHERE id = ?', (assignment_id,))


# === STATISTICS ===
def _active_assignments_where(team_id, start_date, end_date, team_ids=None):
    """WHERE-условие + параметры, общие для выборки активных назначений и их агрегатов"""
    # @formatter:off
    where = '''WHERE a.status IN ('new', 'planned')
                 AND a.is_deleted = 0
                 AND t.task_status NOT IN ('done', 'cancelled')
                 AND t.is_deleted = 0
                 AND a.date BETWEEN ? AND ?'''
    # @formatter:on
    params = [start_date, end_date]

    if team_ids:
        placeholders = ','.join('?' * len(team_ids))
        where += f' AND t.team_id IN ({placeholders})'
        params.extend(team_ids)
    elif team_id:
        where += ' AND t.team_id = ?'
        params.append(team_id)

    return where, params


@with_db_connection(commit_on_success=False)
def get_active_assignments_in_period(conn, team_id, start_date, end_date, team_ids=None, offset=0, limit=None):
    """Получить активные назначения (new/planned) за период с данными задач и сотрудников.

    limit=None возвращает всю выборку без пагинации (используется бейджами планировщика/
    уведомлениями о просрочке, которым нужен полный список, а не одна страница)."""
    where, params = _active_assignments_where(team_id, start_date, end_date, team_ids)
    # @formatter:off
    query = '''SELECT a.id, a.task_id, t.name AS task_name, t.criticality,
                      a.date, a.block, a.status, a.user_id, a.comment,
                      u.last_name  AS user_last_name,
                      u.first_name AS user_first_name,
                      u.middle_name AS user_middle_name,
                      t.team_id, tm.name AS team_name
               FROM assignments a
                   JOIN tasks t ON a.task_id = t.id
                   JOIN teams tm ON t.team_id = tm.id
                   LEFT JOIN users u ON a.user_id = u.id
               ''' + where + '''
               ORDER BY a.date,
                        CASE t.criticality WHEN 'high' THEN 0 WHEN 'medium' THEN 1 WHEN 'low' THEN 2 ELSE 3 END,
                        t.priority DESC, t.name'''
    # @formatter:on
    if limit is not None:
        query += ' LIMIT ? OFFSET ?'
        params = list(params) + [limit, offset]
    return conn.execute(query, tuple(params)).fetchall()


@with_db_connection(commit_on_success=False)
def get_active_assignments_stats(conn, team_id, start_date, end_date, team_ids=None):
    """Итоги по активным назначениям за период (для плиток-счётчиков) — по всей выборке, без LIMIT/OFFSET"""
    where, params = _active_assignments_where(team_id, start_date, end_date, team_ids)
    # @formatter:off
    query = '''SELECT COUNT(*) AS total,
                      SUM(CASE WHEN a.status = 'new' THEN 1 ELSE 0 END) AS status_new,
                      SUM(CASE WHEN a.status = 'planned' THEN 1 ELSE 0 END) AS status_planned,
                      SUM(CASE WHEN t.criticality = 'high' THEN 1 ELSE 0 END) AS crit_high,
                      SUM(CASE WHEN t.criticality = 'medium' THEN 1 ELSE 0 END) AS crit_medium,
                      SUM(CASE WHEN t.criticality = 'low' THEN 1 ELSE 0 END) AS crit_low
               FROM assignments a
                   JOIN tasks t ON a.task_id = t.id
               ''' + where
    # @formatter:on
    row = conn.execute(query, tuple(params)).fetchone()
    return {
        'total': row['total'] or 0,
        'status_new': row['status_new'] or 0,
        'status_planned': row['status_planned'] or 0,
        'crit_high': row['crit_high'] or 0,
        'crit_medium': row['crit_medium'] or 0,
        'crit_low': row['crit_low'] or 0,
    }


# === HISTORY ===
@with_db_connection(commit_on_success=False)
def get_assignment_history(conn, assignment_id, offset=0, limit=20):
    """История изменений конкретного назначения (пока оно существует), новые сверху"""
    # @formatter:off
    rows = conn.execute(
        '''SELECT ah.*,
                  u.last_name AS changed_by_last_name,
                  u.first_name AS changed_by_first_name,
                  u.middle_name AS changed_by_middle_name
           FROM assignment_history ah
               LEFT JOIN users u ON ah.changed_by_user_id = u.id
           WHERE ah.assignment_id = ?
           ORDER BY ah.changed_at DESC, ah.id DESC
           LIMIT ? OFFSET ?''',
        (assignment_id, limit, offset)
    ).fetchall()
    # @formatter:on
    return [dict(r) for r in rows]


@with_db_connection(commit_on_success=False)
def get_assignment_history_count(conn, assignment_id):
    """Общее количество записей истории назначения (для пагинации)"""
    row = conn.execute(
        'SELECT COUNT(*) AS count FROM assignment_history WHERE assignment_id = ?', (assignment_id,)
    ).fetchone()
    return row['count']


@with_db_connection(commit_on_success=False)
def get_task_full_history(conn, task_id, offset=0, limit=20):
    """Объединённая история задачи: её собственные изменения + история всех назначений
    по ней (включая удалённые - assignment_history.task_id денормализован и переживает
    удаление самого назначения). Новые записи сверху."""
    # @formatter:off
    rows = conn.execute(
        '''SELECT * FROM (
               SELECT th.id AS id, th.task_id AS task_id, NULL AS assignment_id, NULL AS date,
                      th.action AS action, th.field_name AS field_name, th.old_value AS old_value,
                      th.new_value AS new_value, th.changed_at AS changed_at,
                      th.changed_by_user_id AS changed_by_user_id, 'task' AS entity,
                      u.last_name AS changed_by_last_name, u.first_name AS changed_by_first_name,
                      u.middle_name AS changed_by_middle_name
               FROM task_history th
                   LEFT JOIN users u ON th.changed_by_user_id = u.id
               WHERE th.task_id = ?
               UNION ALL
               SELECT ah.id AS id, ah.task_id AS task_id, ah.assignment_id AS assignment_id, ah.date AS date,
                      ah.action AS action, ah.field_name AS field_name, ah.old_value AS old_value,
                      ah.new_value AS new_value, ah.changed_at AS changed_at,
                      ah.changed_by_user_id AS changed_by_user_id, 'assignment' AS entity,
                      u.last_name AS changed_by_last_name, u.first_name AS changed_by_first_name,
                      u.middle_name AS changed_by_middle_name
               FROM assignment_history ah
                   LEFT JOIN users u ON ah.changed_by_user_id = u.id
               WHERE ah.task_id = ?
           ) combined
           ORDER BY changed_at DESC, id DESC
           LIMIT ? OFFSET ?''',
        (task_id, task_id, limit, offset)
    ).fetchall()
    # @formatter:on
    return [dict(r) for r in rows]


@with_db_connection(commit_on_success=False)
def get_task_full_history_count(conn, task_id):
    """Общее количество записей объединённой истории задачи (для пагинации)"""
    row = conn.execute(
        '''SELECT (SELECT COUNT(*) FROM task_history WHERE task_id = ?) +
                  (SELECT COUNT(*) FROM assignment_history WHERE task_id = ?) AS count''',
        (task_id, task_id)
    ).fetchone()
    return row['count']


_TEAM_HISTORY_COMBINED_SQL = '''SELECT * FROM (
               SELECT th.id AS id, th.task_id AS task_id, NULL AS assignment_id, NULL AS date,
                      th.action AS action, th.field_name AS field_name, th.old_value AS old_value,
                      th.new_value AS new_value, th.changed_at AS changed_at,
                      th.changed_by_user_id AS changed_by_user_id, 'task' AS entity,
                      t.name AS task_name, t.is_deleted AS task_is_deleted,
                      u.last_name AS changed_by_last_name, u.first_name AS changed_by_first_name,
                      u.middle_name AS changed_by_middle_name
               FROM task_history th
                   JOIN tasks t ON th.task_id = t.id
                   LEFT JOIN users u ON th.changed_by_user_id = u.id
               WHERE t.team_id = ?
               UNION ALL
               SELECT ah.id AS id, ah.task_id AS task_id, ah.assignment_id AS assignment_id, ah.date AS date,
                      ah.action AS action, ah.field_name AS field_name, ah.old_value AS old_value,
                      ah.new_value AS new_value, ah.changed_at AS changed_at,
                      ah.changed_by_user_id AS changed_by_user_id, 'assignment' AS entity,
                      t.name AS task_name, t.is_deleted AS task_is_deleted,
                      u.last_name AS changed_by_last_name, u.first_name AS changed_by_first_name,
                      u.middle_name AS changed_by_middle_name
               FROM assignment_history ah
                   JOIN tasks t ON ah.task_id = t.id
                   LEFT JOIN users u ON ah.changed_by_user_id = u.id
               WHERE t.team_id = ?
           ) combined'''


def _team_history_filter_clause(search, date_from, date_to, changed_by_user_id):
    """Собирает WHERE-условия и параметры для фильтрации журнала команды поверх
    _TEAM_HISTORY_COMBINED_SQL. Используется и выборкой, и подсчётом total, чтобы фильтры
    в обоих местах гарантированно совпадали."""
    conditions = []
    params = []
    if search:
        for word in search.split():
            conditions.append('fuzzy_word_in(task_name, ?)')
            params.append(word)
    if date_from:
        conditions.append('changed_at >= ?')
        params.append(date_from)
    if date_to:
        conditions.append('changed_at <= ?')
        params.append(f'{date_to} 23:59:59')
    if changed_by_user_id:
        conditions.append('changed_by_user_id = ?')
        params.append(changed_by_user_id)
    clause = f"WHERE {' AND '.join(conditions)}" if conditions else ''
    return clause, params


@with_db_connection(commit_on_success=False)
def get_team_history(conn, team_id, offset=0, limit=50, search=None, date_from=None, date_to=None,
                      changed_by_user_id=None):
    """Журнал изменений команды: все изменения задач и назначений по всем задачам команды
    (включая удалённые задачи/назначения — is_deleted теперь отдельный флаг, а не физическое
    удаление, поэтому JOIN на tasks/assignments безопасен и не требует восстановления из JSON).
    Новые записи сверху. Поддерживает фильтры по названию задачи (fuzzy-поиск, как в поиске задач),
    периоду изменения и автору изменения."""
    filter_clause, filter_params = _team_history_filter_clause(search, date_from, date_to, changed_by_user_id)
    # @formatter:off
    rows = conn.execute(
        f'''{_TEAM_HISTORY_COMBINED_SQL}
           {filter_clause}
           ORDER BY changed_at DESC, id DESC
           LIMIT ? OFFSET ?''',
        (team_id, team_id, *filter_params, limit, offset)
    ).fetchall()
    # @formatter:on
    return [dict(r) for r in rows]


@with_db_connection(commit_on_success=False)
def get_team_history_count(conn, team_id, search=None, date_from=None, date_to=None, changed_by_user_id=None):
    """Общее количество записей журнала изменений команды (для пагинации), с учётом тех же
    фильтров, что и get_team_history."""
    filter_clause, filter_params = _team_history_filter_clause(search, date_from, date_to, changed_by_user_id)
    # @formatter:off
    row = conn.execute(
        f'''SELECT COUNT(*) AS count FROM ({_TEAM_HISTORY_COMBINED_SQL}) history_combined
           {filter_clause}''',
        (team_id, team_id, *filter_params)
    ).fetchone()
    # @formatter:on
    return row['count']


# === Инициализация БД при импорте ===
init_db()
