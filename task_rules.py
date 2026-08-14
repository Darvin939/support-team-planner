import json
import os

from api_models import TaskStatus


TERMINAL_TASK_STATUSES: frozenset[TaskStatus] = frozenset({'done', 'cancelled'})


def is_terminal_task_status(status: str | None) -> bool:
    return status in TERMINAL_TASK_STATUSES


def terminal_task_status_sql(column: str, *, negated: bool = False) -> tuple[str, tuple[TaskStatus, ...]]:
    """Build an internal parameterized terminal-status predicate for a trusted SQL column expression."""
    values = tuple(sorted(TERMINAL_TASK_STATUSES))
    placeholders = ', '.join('?' for _ in values)
    operator = 'NOT IN' if negated else 'IN'
    return f'{column} {operator} ({placeholders})', values


with open(
    os.path.join(os.path.dirname(__file__), 'frontend', 'src', 'data', 'taskTransitions.json'),
    encoding='utf-8',
) as transitions_file:
    VALID_TASK_TRANSITIONS = {
        status: set(transitions)
        for status, transitions in json.load(transitions_file).items()
    }


def task_is_locked(task) -> bool:
    return is_terminal_task_status(task['task_status']) or task['is_deleted']
