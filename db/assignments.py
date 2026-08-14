import json
import uuid
from datetime import datetime

from db.connection import backend as _backend, with_db_connection
from task_rules import is_terminal_task_status
from db.errors import BulkAssignmentRescheduleError
from db.tasks import _record_assignment_history

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
def get_assignment_by_id(conn, assignment_id):
    return conn.execute(
        '''SELECT id, task_id, date, block, status, user_id, comment, time_spent, is_deleted
           FROM assignments WHERE id = ?''',
        (assignment_id,),
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


@with_db_connection(commit_on_success=False)
def get_task_completion_suggestion(conn, task_id):
    """Вернуть работу, если назначения полностью и успешно покрывают выбранный шаблон."""
    task = conn.execute(
        '''SELECT t.id, t.name, t.task_status, t.completion_template_id
           FROM tasks t
           JOIN block_templates bt ON bt.id = t.completion_template_id
           WHERE t.id = ? AND t.is_deleted = 0''',
        (task_id,),
    ).fetchone()
    if not task:
        return None

    required_blocks = {
        row['name']
        for row in conn.execute(
            '''SELECT b.name FROM template_blocks tb
               JOIN blocks b ON b.id = tb.block_id
               WHERE tb.template_id = ?''',
            (task['completion_template_id'],),
        ).fetchall()
    }
    if not required_blocks:
        return None

    covered_blocks = set()
    relevant_statuses = []
    assignments = conn.execute(
        'SELECT block, status FROM assignments WHERE task_id = ? AND is_deleted = 0',
        (task_id,),
    ).fetchall()
    for assignment in assignments:
        assignment_blocks = {
            value.strip() for value in (assignment['block'] or '').split(',') if value.strip()
        }
        matched_blocks = assignment_blocks & required_blocks
        if not matched_blocks:
            continue
        covered_blocks.update(matched_blocks)
        relevant_statuses.append(assignment['status'])

    if covered_blocks != required_blocks or not relevant_statuses:
        return None
    if any(status != 'success' for status in relevant_statuses):
        return None
    return {'task_id': task['id'], 'task_name': task['name'], 'task_status': task['task_status']}


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
        f'''SELECT a.id, a.task_id, a.date, a.status, a.is_deleted, t.task_status, t.psi_status,
                   t.is_deleted AS task_is_deleted
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
        if is_terminal_task_status(row['task_status']):
            raise BulkAssignmentRescheduleError(
                'Нельзя изменять назначения завершённой или отменённой задачи')
        if row['psi_status'] == 'required':
            raise BulkAssignmentRescheduleError('Нельзя планировать назначения: требуется пройти ПСИ')
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
