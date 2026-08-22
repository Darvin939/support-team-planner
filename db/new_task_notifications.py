from db.connection import with_db_connection


def _cursor(conn):
    row = conn.execute(
        'SELECT changed_at, id FROM task_history ORDER BY changed_at DESC, id DESC LIMIT 1'
    ).fetchone()
    return (row['changed_at'], row['id']) if row else ('', 0)


def _ensure_state(conn, user_id):
    row = conn.execute('''SELECT new_tasks_seen_at, new_tasks_seen_history_id
                          FROM user_notification_state WHERE user_id = ?''', (user_id,)).fetchone()
    if row:
        return row['new_tasks_seen_at'], row['new_tasks_seen_history_id']
    changed_at, history_id = _cursor(conn)
    conn.execute('''INSERT INTO user_notification_state
                    (user_id, new_tasks_seen_at, new_tasks_seen_history_id) VALUES (?, ?, ?)''',
                 (user_id, changed_at, history_id))
    return changed_at, history_id


def _where(team_ids):
    access_sql = ''
    params = []
    if team_ids is not None:
        if not team_ids:
            access_sql = ' AND 0'
        else:
            access_sql = f" AND t.team_id IN ({','.join('?' for _ in team_ids)})"
            params.extend(team_ids)
    return access_sql, params


@with_db_connection()
def get_new_task_notifications(conn, user_id, team_ids=None, offset=0, limit=30, watermark=None):
    seen_at, seen_id = _ensure_state(conn, user_id)
    watermark = watermark or _cursor(conn)
    watermark_at, watermark_id = watermark
    access_sql, access_params = _where(team_ids)
    base = f'''
        FROM task_history h
        JOIN tasks t ON t.id = h.task_id
        JOIN teams tm ON tm.id = t.team_id
        LEFT JOIN users u ON u.id = h.changed_by_user_id
        WHERE h.action = 'create'
          AND h.id = (SELECT MIN(h2.id) FROM task_history h2 WHERE h2.task_id = h.task_id AND h2.action = 'create')
          AND t.is_deleted = 0
          AND (h.changed_by_user_id IS NULL OR h.changed_by_user_id != ?)
          AND (h.changed_at > ? OR (h.changed_at = ? AND h.id > ?))
          AND (h.changed_at < ? OR (h.changed_at = ? AND h.id <= ?))
          {access_sql}
    '''
    params = [user_id, seen_at, seen_at, seen_id, watermark_at, watermark_at, watermark_id, *access_params]
    total = conn.execute('SELECT COUNT(*) ' + base, params).fetchone()[0]
    rows = conn.execute('''
        SELECT t.id AS task_id, t.team_id, t.name AS task_name, t.criticality,
               t.task_status, tm.name AS team_name, h.changed_at, h.id AS history_id,
               u.last_name AS author_last_name, u.first_name AS author_first_name,
               u.middle_name AS author_middle_name
        ''' + base + ' ORDER BY h.changed_at DESC, h.id DESC LIMIT ? OFFSET ?',
        (*params, limit, offset)).fetchall()
    return {
        'items': [dict(row) for row in rows],
        'total': total,
        'watermark': {'changed_at': watermark_at, 'history_id': watermark_id},
    }


@with_db_connection()
def mark_new_tasks_seen(conn, user_id, changed_at, history_id):
    _ensure_state(conn, user_id)
    conn.execute('''
        UPDATE user_notification_state
           SET new_tasks_seen_at = ?, new_tasks_seen_history_id = ?
         WHERE user_id = ?
           AND (new_tasks_seen_at < ? OR
                (new_tasks_seen_at = ? AND new_tasks_seen_history_id < ?))
    ''', (changed_at, history_id, user_id, changed_at, changed_at, history_id))
    return True
