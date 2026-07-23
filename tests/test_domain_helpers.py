import unittest

from query_parsing import parse_int_csv
from task_rules import task_is_locked


class DomainHelpersTest(unittest.TestCase):
    def test_task_lock_rule(self):
        self.assertTrue(task_is_locked({'task_status': 'done', 'is_deleted': 0}))
        self.assertTrue(task_is_locked({'task_status': 'cancelled', 'is_deleted': 0}))
        self.assertTrue(task_is_locked({'task_status': 'new', 'is_deleted': 1}))
        self.assertFalse(task_is_locked({'task_status': 'new', 'is_deleted': 0}))

    def test_csv_int_parser(self):
        self.assertIsNone(parse_int_csv(None))
        self.assertIsNone(parse_int_csv(''))
        self.assertEqual([1, 2, 3], parse_int_csv('1, 2,,3'))
