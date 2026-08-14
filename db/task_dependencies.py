from db.connection import with_db_connection
from db.tasks import _fuzzy_search_clause
from task_rules import terminal_task_status_sql

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
    src_terminal_clause, terminal_params = terminal_task_status_sql('src.task_status')
    dep_terminal_clause, dep_terminal_params = terminal_task_status_sql('dep.task_status')
    terminal_edge_filter = f'NOT ({src_terminal_clause} AND {dep_terminal_clause})'
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
            (team_id, *params, *params, *terminal_params, *dep_terminal_params)
        ).fetchall()
    else:
        edges = conn.execute(
            f'''SELECT td.task_id, td.depends_on_task_id AS dep_id
                FROM task_dependencies td
                JOIN tasks src ON td.task_id            = src.id
                JOIN tasks dep ON td.depends_on_task_id = dep.id
                WHERE src.team_id = ? AND src.is_deleted = 0 AND dep.is_deleted = 0
                  AND {terminal_edge_filter}''',
            (team_id, *terminal_params, *dep_terminal_params)
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
    active_clause, terminal_params = terminal_task_status_sql('task_status', negated=True)
    params = [team_id, *terminal_params]
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
              AND {active_clause}
              {search_clause}
            ORDER BY name
            LIMIT ?
        )
        {include_clause}
        ORDER BY name
    '''
    # @formatter:on
    return conn.execute(query, params).fetchall()
