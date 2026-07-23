def task_is_locked(task) -> bool:
    return task['task_status'] in ('done', 'cancelled') or task['is_deleted']
