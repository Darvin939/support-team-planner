from backend.db.connection import with_db_connection


_ASSIGNMENT_HISTORY_SQL = '''
    SELECT ah.*, u.last_name AS changed_by_last_name, u.first_name AS changed_by_first_name,
           u.middle_name AS changed_by_middle_name,
           'assignment' AS entity,
           COALESCE(ah.event_id, 'legacy-assignment-' || ah.id) AS event_key
      FROM assignment_history ah
      LEFT JOIN users u ON ah.changed_by_user_id = u.id
     WHERE ah.assignment_id = ?
'''

_TASK_HISTORY_SQL = '''
    SELECT * FROM (
        SELECT th.id AS id, th.event_id AS event_id,
               COALESCE(th.event_id, 'legacy-task-' || th.id) AS event_key,
               th.task_id AS task_id, NULL AS assignment_id, NULL AS date,
               th.action AS action, th.field_name AS field_name, th.old_value AS old_value,
               th.new_value AS new_value, th.changed_at AS changed_at,
               th.changed_by_user_id AS changed_by_user_id, 'task' AS entity,
               u.last_name AS changed_by_last_name, u.first_name AS changed_by_first_name,
               u.middle_name AS changed_by_middle_name
          FROM task_history th
          LEFT JOIN users u ON th.changed_by_user_id = u.id
         WHERE th.task_id = ?
        UNION ALL
        SELECT ah.id AS id, ah.event_id AS event_id,
               COALESCE(ah.event_id, 'legacy-assignment-' || ah.id) AS event_key,
               ah.task_id AS task_id, ah.assignment_id AS assignment_id, ah.date AS date,
               ah.action AS action, ah.field_name AS field_name, ah.old_value AS old_value,
               ah.new_value AS new_value, ah.changed_at AS changed_at,
               ah.changed_by_user_id AS changed_by_user_id, 'assignment' AS entity,
               u.last_name AS changed_by_last_name, u.first_name AS changed_by_first_name,
               u.middle_name AS changed_by_middle_name
          FROM assignment_history ah
          LEFT JOIN users u ON ah.changed_by_user_id = u.id
         WHERE ah.task_id = ?
    )
'''


@with_db_connection(commit_on_success=False)
def get_assignment_history(conn, assignment_id, offset=0, limit=20):
    """Return all rows for a page of assignment events, newest events first."""
    rows = conn.execute(
        f'''WITH history AS ({_ASSIGNMENT_HISTORY_SQL}),
                   page_events AS (
                       SELECT event_key FROM history
                       GROUP BY event_key
                       ORDER BY MAX(changed_at) DESC, MAX(id) DESC, event_key DESC
                       LIMIT ? OFFSET ?
                   )
            SELECT * FROM history
             WHERE event_key IN (SELECT event_key FROM page_events)
             ORDER BY changed_at DESC, id DESC''',
        (assignment_id, limit, offset),
    ).fetchall()
    return [dict(row) for row in rows]


@with_db_connection(commit_on_success=False)
def get_assignment_history_count(conn, assignment_id):
    row = conn.execute(
        f'''WITH history AS ({_ASSIGNMENT_HISTORY_SQL})
            SELECT COUNT(*) AS count FROM (SELECT event_key FROM history GROUP BY event_key)''',
        (assignment_id,),
    ).fetchone()
    return row['count']


@with_db_connection(commit_on_success=False)
def get_task_full_history(conn, task_id, offset=0, limit=20):
    """Return all rows for a page of task and assignment history events."""
    rows = conn.execute(
        f'''WITH history AS ({_TASK_HISTORY_SQL}),
                   page_events AS (
                       SELECT event_key FROM history
                       GROUP BY event_key
                       ORDER BY MAX(changed_at) DESC, MAX(id) DESC, event_key DESC
                       LIMIT ? OFFSET ?
                   )
            SELECT * FROM history
             WHERE event_key IN (SELECT event_key FROM page_events)
             ORDER BY changed_at DESC, id DESC''',
        (task_id, task_id, limit, offset),
    ).fetchall()
    return [dict(row) for row in rows]


@with_db_connection(commit_on_success=False)
def get_task_full_history_count(conn, task_id):
    row = conn.execute(
        f'''WITH history AS ({_TASK_HISTORY_SQL})
            SELECT COUNT(*) AS count FROM (SELECT event_key FROM history GROUP BY event_key)''',
        (task_id, task_id),
    ).fetchone()
    return row['count']


_TEAM_HISTORY_COMBINED_SQL = '''
    SELECT combined.*,
           COALESCE(combined.event_id, 'legacy-' || combined.entity || '-' || combined.id) AS event_key
      FROM (
        SELECT th.id AS id, th.event_id AS event_id, th.task_id AS task_id,
               NULL AS assignment_id, NULL AS date,
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
        SELECT ah.id AS id, ah.event_id AS event_id, ah.task_id AS task_id,
               ah.assignment_id AS assignment_id, ah.date AS date,
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
      ) combined
'''


def _team_history_filter_clause(search, date_from, date_to, changed_by_user_id):
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
    return (f"WHERE {' AND '.join(conditions)}" if conditions else ''), params


@with_db_connection(commit_on_success=False)
def get_team_history(conn, team_id, offset=0, limit=50, search=None, date_from=None, date_to=None,
                     changed_by_user_id=None):
    filter_clause, filter_params = _team_history_filter_clause(search, date_from, date_to, changed_by_user_id)
    rows = conn.execute(
        f'''WITH filtered AS ({_TEAM_HISTORY_COMBINED_SQL} {filter_clause}),
                   page_events AS (
                       SELECT event_key FROM filtered
                       GROUP BY event_key
                       ORDER BY MAX(changed_at) DESC, MAX(id) DESC, event_key DESC
                       LIMIT ? OFFSET ?
                   )
            SELECT * FROM filtered
             WHERE event_key IN (SELECT event_key FROM page_events)
             ORDER BY changed_at DESC, id DESC''',
        (team_id, team_id, *filter_params, limit, offset),
    ).fetchall()
    return [dict(row) for row in rows]


@with_db_connection(commit_on_success=False)
def get_team_history_count(conn, team_id, search=None, date_from=None, date_to=None, changed_by_user_id=None):
    filter_clause, filter_params = _team_history_filter_clause(search, date_from, date_to, changed_by_user_id)
    row = conn.execute(
        f'''WITH filtered AS ({_TEAM_HISTORY_COMBINED_SQL} {filter_clause})
            SELECT COUNT(*) AS count FROM (SELECT event_key FROM filtered GROUP BY event_key)''',
        (team_id, team_id, *filter_params),
    ).fetchone()
    return row['count']
