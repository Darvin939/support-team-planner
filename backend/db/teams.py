from backend.db.connection import backend as _backend, with_db_connection
from backend.db.errors import IntegrityConstraintError
from backend.db.grouping import group_rows
from backend.db.pagination import page_result
from backend.db.search import matching_ids_clause
from backend.db.reference_data import _get_template_blocks_map


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

    tmpls_by_team = {
        team_id: [{'id': row['id'], 'name': row['name']} for row in entries]
        for team_id, entries in group_rows(rows, 'team_id').items()
    }

    return [{'id': t['id'], 'name': t['name'], 'templates': tmpls_by_team.get(t['id'], [])} for t in teams]


@with_db_connection(commit_on_success=False)
def get_teams_for_user(conn, user_id, role):
    if role == 'admin' or not conn.execute(
        f'SELECT 1 FROM user_team_access WHERE user_id = {_backend.placeholder} LIMIT 1', (user_id,)
    ).fetchone():
        teams = conn.execute('SELECT id, name FROM teams ORDER BY name').fetchall()
    else:
        teams = conn.execute(
            f'''SELECT t.id, t.name FROM teams t
               JOIN user_team_access access ON access.team_id = t.id
               WHERE access.user_id = {_backend.placeholder} ORDER BY t.name''', (user_id,)
        ).fetchall()
    rows = conn.execute(
        '''SELECT tt.team_id, bt.id, bt.name FROM team_templates tt
           JOIN block_templates bt ON tt.template_id = bt.id ORDER BY bt.name'''
    ).fetchall()
    allowed = {team['id'] for team in teams}
    templates = {
        team_id: [{'id': row['id'], 'name': row['name']} for row in entries]
        for team_id, entries in group_rows(rows, 'team_id').items()
        if team_id in allowed
    }
    return [{'id': team['id'], 'name': team['name'], 'templates': templates.get(team['id'], [])} for team in teams]


@with_db_connection(commit_on_success=False)
def get_teams_page_for_user(conn, user_id, role, offset=0, limit=20, search=None):
    """Вернуть страницу доступных пользователю команд с разрешёнными шаблонами."""
    needle = (search or '').strip().casefold()
    restricted = role != 'admin' and conn.execute(
        f'SELECT 1 FROM user_team_access WHERE user_id = {_backend.placeholder} LIMIT 1', (user_id,)
    ).fetchone()

    joins = ''
    where = []
    params = []
    if restricted:
        joins = 'JOIN user_team_access access ON access.team_id = t.id'
        where.append(f'access.user_id = {_backend.placeholder}')
        params.append(user_id)
    if needle:
        if _backend.name == 'postgresql':
            access = f"WHERE {' AND '.join(where)}" if where else ''
            clause, search_params = matching_ids_clause(
                conn, _backend, f'SELECT t.id, t.name FROM teams t {joins} {access}', params,
                lambda row: needle in row[1].casefold(), 't.id',
            )
            where.append(clause)
            params.extend(search_params)
        else:
            where.append(f'instr(casefold(t.name), {_backend.placeholder}) > 0')
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
            LIMIT {_backend.placeholder} OFFSET {_backend.placeholder}''',
        (*params, limit, offset),
    ).fetchall()

    templates = {}
    team_ids = [team['id'] for team in teams]
    if team_ids:
        placeholders = _backend.placeholders(len(team_ids))
        rows = conn.execute(
            f'''SELECT tt.team_id, bt.id, bt.name FROM team_templates tt
                JOIN block_templates bt ON tt.template_id = bt.id
                WHERE tt.team_id IN ({placeholders})
                ORDER BY bt.name''',
            team_ids,
        ).fetchall()
        for row in rows:
            templates.setdefault(row['team_id'], []).append({'id': row['id'], 'name': row['name']})

    return page_result(
        [
            {'id': team['id'], 'name': team['name'], 'templates': templates.get(team['id'], [])}
            for team in teams
        ],
        total,
        'teams',
    )


@with_db_connection(write=True)
def grant_team_access_if_restricted(conn, user_id, role, team_id):
    if role == 'admin':
        return
    if conn.execute(f'SELECT 1 FROM user_team_access WHERE user_id = {_backend.placeholder} LIMIT 1', (user_id,)).fetchone():
        conn.execute(f'INSERT INTO user_team_access (user_id, team_id) VALUES ({_backend.placeholder}, {_backend.placeholder}){_backend.conflict_ignore(("user_id", "team_id"))}', (user_id, team_id))


@with_db_connection(commit_on_success=False)
def get_team_by_id(conn, team_id):
    """Получить команду по ID"""
    return conn.execute(f'SELECT id, name FROM teams WHERE id = {_backend.placeholder}', (team_id,)).fetchone()


@with_db_connection(commit_on_success=False)
def get_team_allowed_templates(conn, team_id):
    """Получить шаблоны, разрешённые для команды, вместе с блоками, смещениями и сегментом шаблона
    (segment_id включён в каждый шаблон, чтобы клиент мог сузить список до сегмента конкретной
    задачи — см. AssignmentModal.tsx)"""
    tmpls = conn.execute(
        f'''SELECT bt.id, bt.name, bt.segment_id
           FROM team_templates tt
           JOIN block_templates bt ON tt.template_id = bt.id
           WHERE tt.team_id = {_backend.placeholder}
           ORDER BY bt.name''',
        (team_id,)
    ).fetchall()
    blocks_by_template = _get_template_blocks_map(conn, [template['id'] for template in tmpls])

    result = []
    for t in tmpls:
        result.append({
            'id': t['id'],
            'name': t['name'],
            'segment_id': t['segment_id'],
            'blocks': blocks_by_template.get(t['id'], [])
        })
    return result


@with_db_connection(commit_on_success=False)
def get_blocks_for_team(conn, team_id, segment_id=None):
    """Получить уникальные блоки из разрешённых шаблонов команды, опционально ограниченные
    шаблонами конкретного сегмента"""
    segment_clause = f'AND bt.segment_id = {_backend.placeholder}' if segment_id is not None else ''
    params = [team_id] + ([segment_id] if segment_id is not None else [])
    rows = conn.execute(
        f'''SELECT DISTINCT b.id, b.name
            FROM team_templates tt
            JOIN block_templates bt ON tt.template_id = bt.id
            JOIN template_blocks tb ON tt.template_id = tb.template_id
            JOIN blocks b ON tb.block_id = b.id
            WHERE tt.team_id = {_backend.placeholder}
            {segment_clause}
            ORDER BY b.name ASC''',
        params
    ).fetchall()
    return [{'id': r['id'], 'name': r['name']} for r in rows]


def _set_team_templates(conn, team_id, template_ids):
    """Заменить набор разрешённых шаблонов команды (без коммита)"""
    conn.execute(f'DELETE FROM team_templates WHERE team_id = {_backend.placeholder}', (team_id,))
    for tmpl_id in (template_ids or []):
        try:
            conn.execute(
                f'INSERT INTO team_templates (team_id, template_id) VALUES ({_backend.placeholder}, {_backend.placeholder}){_backend.conflict_ignore(("team_id", "template_id"))}',
                (team_id, int(tmpl_id))
            )
        except (TypeError, ValueError):
            pass


@with_db_connection(write=True)
def create_team(conn, name, template_ids=None):
    """Создать команду"""
    try:
        cursor = _backend.insert_id(conn, f'INSERT INTO teams (name) VALUES ({_backend.placeholder})', (name,))
    except _backend.duplicate_error as exc:
        if not _backend.is_unique(exc):
            raise
        raise IntegrityConstraintError('Команда с таким названием уже существует')
    team_id = cursor
    _set_team_templates(conn, team_id, template_ids)
    return team_id


@with_db_connection(write=True)
def update_team(conn, team_id, name, template_ids=None):
    """Обновить команду и её разрешённые шаблоны"""
    try:
        conn.execute(f'UPDATE teams SET name = {_backend.placeholder} WHERE id = {_backend.placeholder}', (name, team_id))
    except _backend.duplicate_error as exc:
        if not _backend.is_unique(exc):
            raise
        raise IntegrityConstraintError('Команда с таким названием уже существует')
    _set_team_templates(conn, team_id, template_ids)


@with_db_connection(write=True)
def delete_team(conn, team_id):
    """Удалить команду (шаблоны и задачи удаляются каскадно — team_templates.team_id и tasks.team_id
    оба ON DELETE CASCADE, поэтому в отличие от delete_segment здесь физически не может возникнуть
    нарушение внешнего ключа)"""
    conn.execute(f'DELETE FROM teams WHERE id = {_backend.placeholder}', (team_id,))
