from datetime import datetime, timedelta, timezone

from backend.db.connection import backend as _backend, with_db_connection
from backend.task_rules import terminal_task_status_sql

RETENTION_DAYS = 7
MAX_SEEN_TASK_IDS = 100


def _retention_boundary():
    return (datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)).strftime('%Y-%m-%d %H:%M:%S')


def _cursor(conn):
    row = conn.execute(
        'SELECT changed_at, id FROM task_history ORDER BY changed_at DESC, id DESC LIMIT 1'
    ).fetchone()
    return (row['changed_at'], row['id']) if row else ('', 0)


def _ensure_state(conn, user_id):
    row = conn.execute(f'''SELECT new_tasks_seen_at, new_tasks_seen_history_id
                          FROM user_new_task_notification_state WHERE user_id = {_backend.placeholder}''', (user_id,)).fetchone()
    if row:
        return row['new_tasks_seen_at'], row['new_tasks_seen_history_id']
    changed_at, history_id = _cursor(conn)
    conn.execute(f'''INSERT INTO user_new_task_notification_state
                    (user_id, new_tasks_seen_at, new_tasks_seen_history_id) VALUES ({_backend.placeholder}, {_backend.placeholder}, {_backend.placeholder})''',
                 (user_id, changed_at, history_id))
    return changed_at, history_id


def _where(team_ids):
    access_sql = ''
    params = []
    if team_ids is not None:
        if not team_ids:
            access_sql = ' AND FALSE'
        else:
            access_sql = f" AND t.team_id IN ({_backend.placeholders(len(team_ids))})"
            params.extend(team_ids)
    return access_sql, params


@with_db_connection(write=True)
def get_new_task_notifications(conn, user_id, team_ids=None, offset=0, limit=30, watermark=None):
    seen_at, seen_id = _ensure_state(conn, user_id)
    watermark = watermark or _cursor(conn)
    watermark_at, watermark_id = watermark
    access_sql, access_params = _where(team_ids)
    active_task_sql, terminal_statuses = terminal_task_status_sql('t.task_status', negated=True, placeholder=_backend.placeholder)
    base = f'''
        FROM task_history h
        JOIN tasks t ON t.id = h.task_id
        JOIN teams tm ON tm.id = t.team_id
        LEFT JOIN users u ON u.id = h.changed_by_user_id
        LEFT JOIN user_new_task_notification_seen_events seen
          ON seen.task_history_id = h.id AND seen.user_id = {_backend.placeholder}
        WHERE h.action = 'create'
          AND h.id = (SELECT MIN(h2.id) FROM task_history h2 WHERE h2.task_id = h.task_id AND h2.action = 'create')
          AND t.is_deleted = 0
          AND h.changed_at > {_backend.placeholder}
          AND seen.task_history_id IS NULL
          AND (h.changed_by_user_id IS NULL OR h.changed_by_user_id != {_backend.placeholder})
          AND (h.changed_at > {_backend.placeholder} OR (h.changed_at = {_backend.placeholder} AND h.id > {_backend.placeholder}))
          AND (h.changed_at < {_backend.placeholder} OR (h.changed_at = {_backend.placeholder} AND h.id <= {_backend.placeholder}))
          AND {active_task_sql}
          {access_sql}
    '''
    params = [user_id, _retention_boundary(), user_id, seen_at, seen_at, seen_id,
              watermark_at, watermark_at, watermark_id, *terminal_statuses, *access_params]
    total = conn.execute('SELECT COUNT(*) ' + base, params).fetchone()[0]
    rows = conn.execute('''
        SELECT t.id AS task_id, t.team_id, t.name AS task_name, t.criticality,
               t.task_status, tm.name AS team_name, h.changed_at, h.id AS history_id,
               u.last_name AS author_last_name, u.first_name AS author_first_name,
               u.middle_name AS author_middle_name
        ''' + base + f' ORDER BY h.changed_at DESC, h.id DESC LIMIT {_backend.placeholder} OFFSET {_backend.placeholder}',
        (*params, limit, offset)).fetchall()
    return {
        'items': [dict(row) for row in rows],
        'total': total,
        'watermark': {'changed_at': watermark_at, 'history_id': watermark_id},
    }


@with_db_connection(write=True)
def mark_new_tasks_seen(conn, user_id, changed_at, history_id):
    _ensure_state(conn, user_id)
    conn.execute(f'''
        UPDATE user_new_task_notification_state
           SET new_tasks_seen_at = {_backend.placeholder}, new_tasks_seen_history_id = {_backend.placeholder}
         WHERE user_id = {_backend.placeholder}
           AND (new_tasks_seen_at < {_backend.placeholder} OR
                (new_tasks_seen_at = {_backend.placeholder} AND new_tasks_seen_history_id < {_backend.placeholder}))
    ''', (changed_at, history_id, user_id, changed_at, changed_at, history_id))
    return True


@with_db_connection(write=True)
def mark_new_task_items_seen(conn, user_id, task_ids, team_ids=None):
    task_ids = list(dict.fromkeys(task_ids))[:MAX_SEEN_TASK_IDS]
    if not task_ids:
        return 0
    access_sql, access_params = _where(team_ids)
    placeholders = _backend.placeholders(len(task_ids))
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    params = [user_id, now, *task_ids, user_id, _retention_boundary(), *access_params]
    cursor = conn.execute(f'''
        INSERT INTO user_new_task_notification_seen_events (user_id, task_history_id, seen_at)
        SELECT {_backend.placeholder}, h.id, {_backend.placeholder}
          FROM task_history h
          JOIN tasks t ON t.id = h.task_id
          LEFT JOIN users u ON u.id = h.changed_by_user_id
         WHERE h.action = 'create'
           AND h.id = (SELECT MIN(h2.id) FROM task_history h2
                       WHERE h2.task_id = h.task_id AND h2.action = 'create')
           AND h.task_id IN ({placeholders})
           AND (h.changed_by_user_id IS NULL OR h.changed_by_user_id != {_backend.placeholder})
           AND h.changed_at > {_backend.placeholder}
           AND t.is_deleted = 0
           {access_sql}
    {_backend.conflict_ignore(("user_id", "task_history_id"))}''', params)
    return cursor.rowcount


@with_db_connection(write=True)
def cleanup_seen_new_task_events(conn, limit=1000):
    boundary = _retention_boundary()
    cursor = conn.execute(f'''
        DELETE FROM user_new_task_notification_seen_events
         WHERE (user_id, task_history_id) IN (
           SELECT s.user_id, s.task_history_id
             FROM user_new_task_notification_seen_events s
             JOIN task_history h ON h.id = s.task_history_id
            WHERE h.changed_at <= {_backend.placeholder}
            LIMIT {_backend.placeholder}
         )
    ''', (boundary, max(1, min(limit, 10000))))
    return cursor.rowcount
