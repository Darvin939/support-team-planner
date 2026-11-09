from backend.db.connection import backend as _backend, with_db_connection
from backend.task_rules import VALID_TASK_TRANSITIONS


def _block_names(value):
    return {name.strip() for name in (value or '').split(',') if name.strip()}


@with_db_connection(commit_on_success=False)
def get_task_completion_suggestions(conn, task_ids):
    """Готовые работы: текущий шаблон покрыт всей успешной историей."""
    task_ids = sorted(set(task_ids) - {None})
    if not task_ids:
        return {}
    placeholders = _backend.placeholders(len(task_ids))
    tasks = conn.execute(
        f'''SELECT id, name, task_status, completion_template_id FROM tasks
            WHERE id IN ({placeholders}) AND is_deleted = 0''', task_ids,
    ).fetchall()
    required = {}
    for row in conn.execute(
        f'''SELECT t.id, b.name FROM tasks t
            JOIN block_templates bt ON bt.id = t.completion_template_id
            JOIN template_blocks tb ON tb.template_id = bt.id
            JOIN blocks b ON b.id = tb.block_id
            WHERE t.id IN ({placeholders})''', task_ids,
    ).fetchall():
        required.setdefault(row['id'], set()).add(row['name'])
    covered = {}
    for row in conn.execute(
        f'''SELECT task_id, block FROM assignments
            WHERE task_id IN ({placeholders}) AND is_deleted = 0 AND status = 'success' ''', task_ids,
    ).fetchall():
        covered.setdefault(row['task_id'], set()).update(_block_names(row['block']))
    return {
        task['id']: {'task_id': task['id'], 'task_name': task['name'], 'task_status': task['task_status']}
        for task in tasks
        if 'done' in VALID_TASK_TRANSITIONS.get(task['task_status'], set())
        and required.get(task['id'])
        and required[task['id']].issubset(covered.get(task['id'], set()))
    }


def get_task_completion_suggestion(task_id):
    return get_task_completion_suggestions([task_id]).get(task_id)
