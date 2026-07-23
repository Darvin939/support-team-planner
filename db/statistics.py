from db.connection import with_db_connection

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
