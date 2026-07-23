from db.connection import with_db_connection

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
