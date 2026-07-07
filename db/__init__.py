import json
from datetime import datetime, timedelta
from functools import wraps

from db.backend import DBBackend
from db.sqlite import SQLiteBackend

_backend: DBBackend = SQLiteBackend()


def get_db_connection():
    conn = _backend.connect()
    _backend.setup_connection(conn)
    return conn


def with_db_connection(default_return=None, raise_on_error=True, commit_on_success=True):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            conn = get_db_connection()
            try:
                result = func(conn, *args, **kwargs)
                if commit_on_success:
                    conn.commit()
                return result
            except _backend.db_error:
                if raise_on_error:
                    raise
                return default_return
            finally:
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
def get_team_by_id(conn, team_id):
    """Получить команду по ID"""
    return conn.execute('SELECT id, name FROM teams WHERE id = ?', (team_id,)).fetchone()


@with_db_connection(commit_on_success=False)
def get_team_allowed_templates(conn, team_id):
    """Получить шаблоны, разрешённые для команды, вместе с блоками и смещениями"""
    tmpls = conn.execute(
        '''SELECT bt.id, bt.name
           FROM team_templates tt
           JOIN block_templates bt ON tt.template_id = bt.id
           WHERE tt.team_id = ?
           ORDER BY bt.name''',
        (team_id,)
    ).fetchall()

    result = []
    for t in tmpls:
        blocks = conn.execute(
            '''SELECT b.id, b.name, tb.schedule_offset AS shift_days
               FROM template_blocks tb
               JOIN blocks b ON tb.block_id = b.id
               WHERE tb.template_id = ?
               ORDER BY tb.schedule_offset ASC, b.name ASC''',
            (t['id'],)
        ).fetchall()
        result.append({
            'id': t['id'],
            'name': t['name'],
            'blocks': [{'id': b['id'], 'name': b['name'], 'shift_days': b['shift_days']} for b in blocks]
        })
    return result


@with_db_connection(commit_on_success=False)
def get_blocks_for_team(conn, team_id):
    """Получить уникальные блоки из разрешённых шаблонов команды"""
    rows = conn.execute(
        '''SELECT DISTINCT b.id, b.name
           FROM team_templates tt
           JOIN template_blocks tb ON tt.template_id = tb.template_id
           JOIN blocks b ON tb.block_id = b.id
           WHERE tt.team_id = ?
           ORDER BY b.name ASC''',
        (team_id,)
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


@with_db_connection(commit_on_success=False)
def create_team(conn, name, template_ids=None):
    """Создать команду"""
    cursor = conn.execute('INSERT INTO teams (name) VALUES (?)', (name,))
    team_id = _backend.last_insert_id(cursor)
    _set_team_templates(conn, team_id, template_ids)
    conn.commit()
    return team_id


@with_db_connection()
def update_team(conn, team_id, name, template_ids=None):
    """Обновить команду и её разрешённые шаблоны"""
    conn.execute('UPDATE teams SET name = ? WHERE id = ?', (name, team_id))
    _set_team_templates(conn, team_id, template_ids)


@with_db_connection()
def delete_team(conn, team_id):
    """Удалить команду (шаблоны и задачи удаляются каскадно)"""
    conn.execute('DELETE FROM teams WHERE id = ?', (team_id,))


# === BLOCKS CRUD ===
@with_db_connection(commit_on_success=False)
def get_all_blocks(conn):
    """Получить все блоки"""
    rows = conn.execute('SELECT id, name FROM blocks ORDER BY name').fetchall()
    return [{'id': r['id'], 'name': r['name']} for r in rows]


@with_db_connection(commit_on_success=False)
def create_block(conn, name):
    """Создать блок"""
    name = name.strip().upper()
    cursor = conn.execute('INSERT INTO blocks (name) VALUES (?)', (name,))
    conn.commit()
    return _backend.last_insert_id(cursor)


@with_db_connection()
def delete_block(conn, block_id):
    """Удалить блок"""
    conn.execute('DELETE FROM blocks WHERE id = ?', (block_id,))


# === BLOCK TEMPLATES CRUD ===
@with_db_connection(commit_on_success=False)
def get_all_templates(conn):
    """Получить все шаблоны блоков с их блоками и смещениями"""
    tmpls = conn.execute('SELECT id, name FROM block_templates ORDER BY name').fetchall()
    result = []
    for t in tmpls:
        blocks = conn.execute(
            '''SELECT b.id, b.name, tb.schedule_offset AS shift_days
               FROM template_blocks tb
               JOIN blocks b ON tb.block_id = b.id
               WHERE tb.template_id = ?
               ORDER BY tb.schedule_offset ASC, b.name ASC''',
            (t['id'],)
        ).fetchall()
        result.append({
            'id': t['id'],
            'name': t['name'],
            'blocks': [{'id': b['id'], 'name': b['name'], 'shift_days': b['shift_days']} for b in blocks]
        })
    return result


@with_db_connection(commit_on_success=False)
def get_template_by_id(conn, template_id):
    """Получить шаблон по ID с блоками"""
    t = conn.execute('SELECT id, name FROM block_templates WHERE id = ?', (template_id,)).fetchone()
    if not t:
        return None
    blocks = conn.execute(
        '''SELECT b.id, b.name, tb.schedule_offset AS shift_days
           FROM template_blocks tb
           JOIN blocks b ON tb.block_id = b.id
           WHERE tb.template_id = ?
           ORDER BY tb.schedule_offset ASC, b.name ASC''',
        (template_id,)
    ).fetchall()
    return {
        'id': t['id'],
        'name': t['name'],
        'blocks': [{'id': b['id'], 'name': b['name'], 'shift_days': b['shift_days']} for b in blocks]
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


@with_db_connection(commit_on_success=False)
def create_template(conn, name, entries=None):
    """Создать шаблон блоков"""
    cursor = conn.execute('INSERT INTO block_templates (name) VALUES (?)', (name.strip(),))
    template_id = _backend.last_insert_id(cursor)
    _set_template_blocks(conn, template_id, entries)
    conn.commit()
    return template_id


@with_db_connection()
def update_template(conn, template_id, name, entries=None):
    """Обновить шаблон и его блоки"""
    conn.execute('UPDATE block_templates SET name = ? WHERE id = ?', (name.strip(), template_id))
    _set_template_blocks(conn, template_id, entries)


@with_db_connection()
def delete_template(conn, template_id):
    """Удалить шаблон (записи template_blocks удаляются каскадно)"""
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
        result.append(u_dict)
    return result


@with_db_connection(commit_on_success=False)
def get_user(conn, user_id):
    """Получить одного пользователя по id (используется, например, GET /api/me)"""
    row = conn.execute(
        'SELECT id, last_name, first_name, middle_name, role FROM users WHERE id = ?', (user_id,)).fetchone()
    return dict(row) if row else None


@with_db_connection(default_return=None, raise_on_error=False, commit_on_success=False)
def create_user(conn, last_name, first_name, middle_name=None, password_hash=None, role='user', login=None,
                 is_assignee=True):
    """Создать пользователя. Возвращает None при нарушении UNIQUE (дубль логина) —
    raise_on_error=False нужен именно для этого: без него IntegrityError улетал бы наверх
    необработанным, и вызывающий код никогда не увидел бы свою ветку "уже существует"."""
    cursor = conn.execute(
        '''INSERT INTO users (last_name, first_name, middle_name, password_hash, role, login, is_assignee)
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (last_name, first_name, middle_name, password_hash, role, login, int(is_assignee)))
    conn.commit()
    return _backend.last_insert_id(cursor)


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
                 is_assignee=True):
    """Обновить пользователя. password_hash=None означает "не менять пароль", login=None — "не менять логин".
    Для учётной записи администратора по умолчанию ФИО и роль никогда не перезаписываются этой
    функцией (можно поменять только пароль и логин) — независимо от того, что пришло в
    last_name/first_name/middle_name/role, чтобы не зависеть от того, отправил ли клиент эти поля вообще."""
    current = conn.execute('SELECT login FROM users WHERE id = ?', (user_id,)).fetchone()
    if not current:
        return False

    if _is_bootstrap_admin(current):
        _update_login_and_password(conn, user_id, password_hash, login)
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
@with_db_connection(commit_on_success=False)
def get_tasks_by_team(conn, team_id, offset=0, limit=10, search=None, show_completed=False, task_id=None):
    """Получить задачи команды с пагинацией и поиском"""
    completed_clause = "" if show_completed else "AND task_status NOT IN ('done', 'cancelled')"
    params = [team_id]
    if search:
        words = search.split()
        word_clauses = " AND ".join(
            "(fuzzy_word_in(name, ?) OR fuzzy_word_in(description, ?))" for _ in words
        )
        search_clause = f"AND ({word_clauses})"
        for word in words:
            params += [word, word]
    else:
        search_clause = ""
    id_clause = ""
    if task_id:
        id_clause = "AND id = ?"
        params.append(task_id)
    params += [limit, offset]
    # @formatter:off
    return conn.execute(
        f'''SELECT id, name, description, criticality, task_status
            FROM tasks
            WHERE team_id = ?
              AND is_deleted = 0
            {completed_clause}
            {search_clause}
            {id_clause}
            ORDER BY CASE criticality
                         WHEN 'high'   THEN 0
                         WHEN 'medium' THEN 1
                         WHEN 'low'    THEN 2
                         ELSE 3
                         END,
                     CASE task_status
                         WHEN 'in_progress' THEN 0
                         WHEN 'ready'       THEN 1
                         WHEN 'new'         THEN 2
                         WHEN 'done'        THEN 3
                         WHEN 'cancelled'   THEN 4
                         ELSE 5
                         END,
                     id
            LIMIT ? OFFSET ?''',
        params
    ).fetchall()
    # @formatter:on


@with_db_connection(commit_on_success=False)
def get_tasks_count_by_team(conn, team_id, search=None, show_completed=False):
    """Получить общее количество задач команды (с учётом поиска)"""
    completed_clause = "" if show_completed else "AND task_status NOT IN ('done', 'cancelled')"
    params = [team_id]
    if search:
        words = search.split()
        word_clauses = " AND ".join(
            "(fuzzy_word_in(name, ?) OR fuzzy_word_in(description, ?))" for _ in words
        )
        search_clause = f"AND ({word_clauses})"
        for word in words:
            params += [word, word]
    else:
        search_clause = ""
    return conn.execute(
        f"SELECT COUNT(*) FROM tasks WHERE team_id = ? AND is_deleted = 0 {completed_clause} {search_clause}",
        params
    ).fetchone()[0]


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
def create_or_update_task(conn, task_id, team_id, name, description, criticality='medium', changed_by=None):
    """Создать или обновить задачу"""
    existing = conn.execute('SELECT name, description, criticality FROM tasks WHERE id = ?', (task_id,)).fetchone()
    if existing:
        for field, new_val in (('name', name), ('description', description), ('criticality', criticality)):
            old_val = existing[field]
            if old_val != new_val:
                _record_task_history(conn, task_id, 'update', field_name=field,
                                      old_value=old_val, new_value=new_val, changed_by=changed_by)
        conn.execute(
            '''UPDATE tasks
               SET name        = ?,
                   description = ?,
                   criticality = ?
               WHERE id = ?''',
            (name, description, criticality, task_id)
        )
        conn.commit()
    else:
        cursor = conn.execute(
            'INSERT INTO tasks (team_id, name, description, criticality) VALUES (?, ?, ?, ?)',
            (team_id, name, description, criticality)
        )
        task_id = _backend.last_insert_id(cursor)
        snapshot = json.dumps({'team_id': team_id, 'name': name, 'description': description,
                                'criticality': criticality}, ensure_ascii=False)
        _record_task_history(conn, task_id, 'create', new_value=snapshot, changed_by=changed_by)
        conn.commit()
    return task_id


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
    """Получить статус задачи и признак её удаления по ID назначения"""
    return conn.execute(
        'SELECT t.task_status, t.is_deleted FROM assignments a JOIN tasks t ON a.task_id = t.id WHERE a.id = ?',
        (assignment_id,)
    ).fetchone()


@with_db_connection()
def update_task_status(conn, task_id, new_status, changed_by=None):
    """Обновить статус задачи"""
    current = conn.execute("SELECT task_status FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if current and current['task_status'] != new_status:
        _record_task_history(conn, task_id, 'update', field_name='task_status',
                              old_value=current['task_status'], new_value=new_status, changed_by=changed_by)
    conn.execute("UPDATE tasks SET task_status = ? WHERE id = ?", (new_status, task_id))
    return True


@with_db_connection()
def maybe_advance_task_to_in_progress(conn, task_id):
    """Автоматически переводит задачу в in_progress если есть плановое назначение"""
    task = conn.execute("SELECT task_status FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if task and task['task_status'] in ('new', 'ready'):
        has_planned = conn.execute(
            "SELECT 1 FROM assignments WHERE task_id = ? AND status = 'planned'", (task_id,)
        ).fetchone()
        if has_planned:
            conn.execute("UPDATE tasks SET task_status = 'in_progress' WHERE id = ?", (task_id,))
    return True


# === TASK DEPENDENCIES ===

@with_db_connection(commit_on_success=False)
def get_all_deps_for_team(conn, team_id, task_ids=None):
    """Получить зависимости задач команды (опционально ограниченные списком task_ids)"""
    if task_ids is not None and len(task_ids) == 0:
        return []
    # @formatter:off
    query = '''SELECT td.task_id, td.depends_on_task_id AS dep_id,
                      dep.name AS dep_name, dep.task_status AS dep_status, dep.is_deleted AS dep_is_deleted
               FROM task_dependencies td
               JOIN tasks src ON td.task_id            = src.id
               JOIN tasks dep ON td.depends_on_task_id = dep.id
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
        conn.execute(
            'INSERT OR IGNORE INTO task_dependencies (task_id, depends_on_task_id) VALUES (?, ?)',
            (task_id, dep_id)
        )


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


@with_db_connection(commit_on_success=False)
def get_active_tasks_flat(conn, team_id, search=None, limit=50, include_ids=None):
    params = [team_id]
    if search:
        words = search.split()
        word_clauses = " AND ".join(
            "(fuzzy_word_in(name, ?) OR fuzzy_word_in(description, ?))" for _ in words
        )
        search_clause = f"AND ({word_clauses})"
        for word in words:
            params += [word, word]
    else:
        search_clause = ""
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
                  a.is_psi,
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
                      a.is_psi,
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
                                 is_psi=0, time_spent=None, changed_by=None):
    """Создать или обновить назначение"""
    existing = conn.execute('SELECT * FROM assignments WHERE id = ?', (assignment_id,)).fetchone()

    new_values = {'date': date_str, 'task_id': task_id, 'block': block, 'status': status,
                  'user_id': user_id, 'comment': comment, 'is_psi': is_psi, 'time_spent': time_spent}

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
                   is_psi      = ?,
                   time_spent  = ?
               WHERE id = ?''',
            (date_str, task_id, block, status, user_id, comment, is_psi, time_spent, assignment_id)
        )
    else:
        cursor = conn.execute(
            '''INSERT INTO assignments (task_id, date, block, status, user_id, comment, is_psi, time_spent)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (task_id, date_str, block, status, user_id, comment, is_psi, time_spent)
        )
        new_assignment_id = _backend.last_insert_id(cursor)
        snapshot = json.dumps(new_values, ensure_ascii=False, default=str)
        _record_assignment_history(conn, new_assignment_id, task_id, date_str, 'create',
                                    new_value=snapshot, changed_by=changed_by)


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
                      a.date, a.block, a.status, a.user_id, a.comment, a.is_psi,
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
                        t.name'''
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
def get_task_history(conn, task_id):
    """История изменений самой задачи (без назначений)"""
    # @formatter:off
    rows = conn.execute(
        '''SELECT th.*,
                  u.last_name AS changed_by_last_name,
                  u.first_name AS changed_by_first_name,
                  u.middle_name AS changed_by_middle_name
           FROM task_history th
               LEFT JOIN users u ON th.changed_by_user_id = u.id
           WHERE th.task_id = ?
           ORDER BY th.changed_at, th.id''',
        (task_id,)
    ).fetchall()
    # @formatter:on
    return [dict(r) for r in rows]


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
