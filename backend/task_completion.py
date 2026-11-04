from backend import db


def completion_result(before, task_ids, role):
    """Предложения только для вновь готовых работ после успешной операции."""
    after = db.get_task_completion_suggestions(task_ids)
    if role not in ('admin', 'editor'):
        return {}
    suggestions = [
        {'task_id': value['task_id'], 'task_name': value['task_name']}
        for task_id, value in after.items() if task_id not in before
    ]
    if not suggestions:
        return {}
    result = {'task_completion_suggestions': suggestions}
    if len(suggestions) == 1:
        result['task_completion_suggestion'] = suggestions[0]
    return result
