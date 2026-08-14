import db
from task_rules import is_terminal_task_status


class TaskDependencyCycleError(Exception):
    pass


class TaskDependencyEditError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


def validate_task_dependency_edit(task_id: int, depends_on_task_id: int) -> None:
    task, dep_task = db.get_tasks_for_dependency_edit(task_id, depends_on_task_id)
    if not task or not dep_task or task['is_deleted'] or dep_task['is_deleted']:
        raise TaskDependencyEditError('Задача не найдена', 404)
    if task['team_id'] != dep_task['team_id']:
        raise TaskDependencyEditError('Задачи принадлежат разным командам', 400)
    if is_terminal_task_status(task['task_status']):
        raise TaskDependencyEditError(
            'Нельзя редактировать завершённую или отменённую задачу',
            400,
        )
