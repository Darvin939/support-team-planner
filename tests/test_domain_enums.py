import ast
import unittest
from pathlib import Path
from typing import get_args

from pydantic import ValidationError

from api_models import (
    AssignmentIn,
    AssignmentStatus,
    Criticality,
    TaskIn,
    TaskStatus,
    TaskStatusIn,
    UserIn,
    UserRole,
)


ROOT = Path(__file__).resolve().parents[1]


def tuple_assignment(path: Path, name: str) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            return tuple(value)
    raise AssertionError(f'{name} not found in {path}')


class DomainEnumContractTest(unittest.TestCase):
    def test_literal_vocabularies_are_current(self):
        self.assertEqual(('new', 'done', 'cancelled'), get_args(TaskStatus))
        self.assertEqual(
            ('new', 'planned', 'rollback', 'success', 'cancelled'),
            get_args(AssignmentStatus),
        )
        self.assertEqual(('low', 'medium', 'high'), get_args(Criticality))
        self.assertEqual(('user', 'editor', 'admin'), get_args(UserRole))

    def test_input_models_reject_unknown_enum_values(self):
        cases = (
            (TaskStatusIn, {'status': 'in_progress'}),
            (AssignmentIn, {'status': 'unknown'}),
            (TaskIn, {'criticality': 'urgent'}),
            (UserIn, {'role': 'owner'}),
        )
        for model, payload in cases:
            with self.subTest(model=model.__name__), self.assertRaises(ValidationError):
                model.model_validate(payload)

    def test_input_models_accept_every_current_enum_value(self):
        for value in get_args(TaskStatus):
            self.assertEqual(value, TaskStatusIn(status=value).status)
        for value in get_args(AssignmentStatus):
            self.assertEqual(value, AssignmentIn(status=value).status)
        for value in get_args(Criticality):
            self.assertEqual(value, TaskIn(criticality=value).criticality)
        for value in get_args(UserRole):
            self.assertEqual(value, UserIn(role=value).role)

    def test_demo_seeds_only_declare_current_task_statuses(self):
        expected = set(get_args(TaskStatus))
        for filename in ('seed_demo_data.py', 'seed_large_demo_data.py'):
            statuses = tuple_assignment(ROOT / filename, 'TASK_STATUSES')
            with self.subTest(filename=filename):
                self.assertEqual(expected, set(statuses))
                self.assertNotIn('ready', statuses)
                self.assertNotIn('in_progress', statuses)


if __name__ == '__main__':
    unittest.main()
