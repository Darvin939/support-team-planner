from db.connection import backend as _backend, with_db_connection
from db.errors import DuplicateEntityError, EntityNotFoundError
from db.tasks import _record_assignment_history
from db.grouping import group_rows
from db.pagination import page_result

# === USERS CRUD ===
@with_db_connection(commit_on_success=False)
def user_exists(conn, user_id):
    """Проверить существование пользователя и получить его роль (используется зависимостью
    get_current_user: сессия может пережить удаление пользователя или пересоздание БД)."""
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


def _get_user_team_ids_map(conn, user_ids):
    if not user_ids:
        return {}
    placeholders = ','.join('?' * len(user_ids))
    rows = conn.execute(
        f'''SELECT user_id, team_id
            FROM user_team_access
            WHERE user_id IN ({placeholders})
            ORDER BY user_id, team_id''',
        user_ids,
    ).fetchall()
    return {
        user_id: [row['team_id'] for row in entries]
        for user_id, entries in group_rows(rows, 'user_id').items()
    }


def _user_search_filter(search):
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
    return (f'WHERE instr(casefold({searchable_text}), ?) > 0', (needle,)) if needle else ('', ())


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
    team_ids_by_user = _get_user_team_ids_map(conn, [user['id'] for user in users])
    result = []
    for u in users:
        u_dict = dict(u)
        u_dict['is_assignee'] = bool(u_dict['is_assignee'])
        u_dict['is_protected'] = _is_bootstrap_admin(u)
        u_dict['team_ids'] = team_ids_by_user.get(u['id'], [])
        result.append(u_dict)
    return result


@with_db_connection(commit_on_success=False)
def get_users_page(conn, offset=0, limit=20, search=None):
    """Отфильтровать пользователей и вернуть только запрошенную страницу."""
    where_clause, filter_params = _user_search_filter(search)
    total = conn.execute(f'SELECT COUNT(*) FROM users {where_clause}', filter_params).fetchone()[0]
    page = conn.execute(
        f'''SELECT id, last_name, first_name, middle_name, role, login, is_assignee
            FROM users
            {where_clause}
            ORDER BY last_name, first_name, middle_name
            LIMIT ? OFFSET ?''',
        (*filter_params, limit, offset),
    ).fetchall()
    team_ids_by_user = _get_user_team_ids_map(conn, [user['id'] for user in page])
    result = []
    for user in page:
        user_dict = dict(user)
        user_dict['is_assignee'] = bool(user_dict['is_assignee'])
        user_dict['is_protected'] = _is_bootstrap_admin(user)
        user_dict['team_ids'] = team_ids_by_user.get(user['id'], [])
        result.append(user_dict)
    return page_result(result, total, 'users')


@with_db_connection(commit_on_success=False)
def get_user(conn, user_id):
    """Получить одного пользователя по id (используется, например, GET /api/me)"""
    row = conn.execute(
        'SELECT id, last_name, first_name, middle_name, role FROM users WHERE id = ?', (user_id,)).fetchone()
    return dict(row) if row else None


@with_db_connection()
def create_user(conn, last_name, first_name, middle_name=None, password_hash=None, role='user', login=None,
                 is_assignee=True, team_ids=None):
    """Создать пользователя. Возвращает None при нарушении UNIQUE (дубль логина) —
    raise_on_error=False нужен именно для этого: без него IntegrityError улетал бы наверх
    необработанным, и вызывающий код никогда не увидел бы свою ветку "уже существует"."""
    try:
        cursor = conn.execute(
            '''INSERT INTO users (last_name, first_name, middle_name, password_hash, role, login, is_assignee)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (last_name, first_name, middle_name, password_hash, role, login, int(is_assignee)))
        user_id = _backend.last_insert_id(cursor)
        _set_user_team_ids(conn, user_id, team_ids, role)
    except _backend.duplicate_error as exc:
        raise DuplicateEntityError('Пользователь с таким логином уже существует') from exc
    return user_id


def _update_login_and_password(conn, user_id, password_hash=None, login=None):
    """Обновить только login/password_hash, не трогая ФИО/роль — используется только веткой
    бутстрап-админа в update_user (для собственного пароля пользователь пользуется отдельной
    update_own_password, которая логин не трогает вовсе)."""
    if password_hash is not None:
        conn.execute('UPDATE users SET password_hash = ? WHERE id = ?', (password_hash, user_id))
    if login is not None:
        conn.execute('UPDATE users SET login = ? WHERE id = ?', (login, user_id))


@with_db_connection()
def update_own_password(conn, user_id, password_hash):
    """Пользователь меняет пароль своей же учётной записи (не через админский update_user) —
    логин, ФИО и роль этой функцией не затрагиваются: логин теперь может менять только admin."""
    cursor = conn.execute('UPDATE users SET password_hash = ? WHERE id = ?', (password_hash, user_id))
    if cursor.rowcount == 0:
        raise EntityNotFoundError('Пользователь не найден')
    return True


def _update_user(conn, user_id, last_name, first_name, middle_name=None, password_hash=None, role='user', login=None,
                 is_assignee=True, team_ids=None):
    """Обновить пользователя. password_hash=None означает "не менять пароль", login=None — "не менять логин".
    Для учётной записи администратора по умолчанию ФИО и роль никогда не перезаписываются этой
    функцией (можно поменять только пароль и логин) — независимо от того, что пришло в
    last_name/first_name/middle_name/role, чтобы не зависеть от того, отправил ли клиент эти поля вообще."""
    current = conn.execute('SELECT login FROM users WHERE id = ?', (user_id,)).fetchone()
    if not current:
        raise EntityNotFoundError('Пользователь не найден')

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


@with_db_connection()
def update_user(conn, user_id, last_name, first_name, middle_name=None, password_hash=None, role='user', login=None,
                is_assignee=True, team_ids=None):
    try:
        return _update_user(
            conn, user_id, last_name, first_name, middle_name, password_hash, role, login, is_assignee, team_ids,
        )
    except _backend.duplicate_error as exc:
        raise DuplicateEntityError('Пользователь с таким логином уже существует') from exc


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
