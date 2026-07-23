import unittest
from unittest.mock import patch

from query_parsing import parse_int_csv
from task_dependency_rules import TaskDependencyEditError, validate_task_dependency_edit
from task_rules import VALID_TASK_TRANSITIONS, task_is_locked


class DomainHelpersTest(unittest.TestCase):
    def test_task_lock_rule(self):
        self.assertTrue(task_is_locked({'task_status': 'done', 'is_deleted': 0}))
        self.assertTrue(task_is_locked({'task_status': 'cancelled', 'is_deleted': 0}))
        self.assertTrue(task_is_locked({'task_status': 'new', 'is_deleted': 1}))
        self.assertFalse(task_is_locked({'task_status': 'new', 'is_deleted': 0}))

    def test_task_transition_rules_are_loaded_from_shared_source(self):
        self.assertEqual({'new': {'done', 'cancelled'}}, VALID_TASK_TRANSITIONS)

    def test_csv_int_parser(self):
        self.assertIsNone(parse_int_csv(None))
        self.assertIsNone(parse_int_csv(''))
        self.assertEqual([1, 2, 3], parse_int_csv('1, 2,,3'))

    def test_dependency_edit_rule_accepts_active_tasks_from_same_team(self):
        task = {'team_id': 1, 'task_status': 'new', 'is_deleted': 0}
        dependency = {'team_id': 1, 'task_status': 'done', 'is_deleted': 0}
        with patch(
            'task_dependency_rules.db.get_tasks_for_dependency_edit',
            return_value=(task, dependency),
        ):
            self.assertIsNone(validate_task_dependency_edit(10, 11))

    def test_dependency_edit_rule_rejects_missing_or_deleted_tasks(self):
        cases = (
            (None, None),
            (
                {'team_id': 1, 'task_status': 'new', 'is_deleted': 1},
                {'team_id': 1, 'task_status': 'new', 'is_deleted': 0},
            ),
        )
        for tasks in cases:
            with self.subTest(tasks=tasks), patch(
                'task_dependency_rules.db.get_tasks_for_dependency_edit',
                return_value=tasks,
            ):
                with self.assertRaisesRegex(TaskDependencyEditError, 'Задача не найдена') as raised:
                    validate_task_dependency_edit(10, 11)
                self.assertEqual(404, raised.exception.status_code)

    def test_dependency_edit_rule_rejects_cross_team_and_terminal_task(self):
        cases = (
            (
                {'team_id': 1, 'task_status': 'new', 'is_deleted': 0},
                {'team_id': 2, 'task_status': 'new', 'is_deleted': 0},
                'Задачи принадлежат разным командам',
            ),
            (
                {'team_id': 1, 'task_status': 'done', 'is_deleted': 0},
                {'team_id': 1, 'task_status': 'new', 'is_deleted': 0},
                'Нельзя редактировать завершённую или отменённую задачу',
            ),
        )
        for task, dependency, message in cases:
            with self.subTest(message=message), patch(
                'task_dependency_rules.db.get_tasks_for_dependency_edit',
                return_value=(task, dependency),
            ):
                with self.assertRaisesRegex(TaskDependencyEditError, message) as raised:
                    validate_task_dependency_edit(10, 11)
                self.assertEqual(400, raised.exception.status_code)
