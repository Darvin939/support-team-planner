import inspect
import unittest

import db
import db.connection
import db.sqlite


class DatabaseModuleBoundaryTest(unittest.TestCase):
    def test_public_dao_signature_hides_injected_connection(self):
        self.assertEqual([], list(inspect.signature(db.get_all_teams).parameters))
        self.assertEqual(
            ['team_id', 'offset', 'limit', 'search', 'include_recent_completed'],
            list(inspect.signature(db.get_tasks_by_team).parameters),
        )

    def test_sqlite_backend_is_selected_only_at_connection_boundary(self):
        source = inspect.getsource(db.connection)
        self.assertIn('from db.sqlite import SQLiteBackend', source)
        for module_name in (
            'assignments', 'freeze_days', 'history', 'reference_data', 'statistics',
            'task_dependencies', 'tasks', 'teams', 'users',
        ):
            module = __import__(f'db.{module_name}', fromlist=['*'])
            self.assertNotIn('db.sqlite', inspect.getsource(module))

    def test_sqlite_backend_does_not_contain_schema_or_migration_sql(self):
        source = inspect.getsource(db.sqlite)
        self.assertNotIn('CREATE TABLE', source)
        self.assertNotIn('ALTER TABLE', source)
        self.assertNotIn('import auth', source)


if __name__ == '__main__':
    unittest.main()
