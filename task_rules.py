import json
import os


with open(
    os.path.join(os.path.dirname(__file__), 'frontend', 'src', 'data', 'taskTransitions.json'),
    encoding='utf-8',
) as transitions_file:
    VALID_TASK_TRANSITIONS = {
        status: set(transitions)
        for status, transitions in json.load(transitions_file).items()
    }


def task_is_locked(task) -> bool:
    return task['task_status'] in ('done', 'cancelled') or task['is_deleted']
