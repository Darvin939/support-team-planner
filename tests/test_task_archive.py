import os
import sqlite3
import tempfile
import unittest

from fastapi.testclient import TestClient

import auth
import db
import db.sqlite as sqlite_backend
from db.sqlite import SQLiteBackend
from support_planner import app


class CompletedAtMigrationTest(unittest.TestCase):
    def test_migration_backfills_only_terminal_tasks_with_history(self):
        conn = sqlite3.connect(':memory:')
        conn.executescript('''
            CREATE TABLE tasks (id INTEGER PRIMARY KEY, team_id INTEGER, task_status TEXT);
            CREATE TABLE task_history (
                id INTEGER PRIMARY KEY, task_id INTEGER, field_name TEXT,
                new_value TEXT, changed_at TEXT
            );
            INSERT INTO tasks VALUES (1, 1, 'done'), (2, 1, 'cancelled'), (3, 1, 'new');
            INSERT INTO task_history VALUES
                (1, 1, 'task_status', 'done', '2026-05-01 10:00:00'),
                (2, 1, 'task_status', 'done', '2026-06-01 10:00:00'),
                (3, 3, 'task_status', 'done', '2026-07-01 10:00:00');
        ''')

        SQLiteBackend._migrate_add_task_completed_at(conn)
        SQLiteBackend._migrate_add_task_completed_at(conn)

        rows = dict(conn.execute('SELECT id, completed_at FROM tasks').fetchall())
        self.assertEqual('2026-06-01 10:00:00', rows[1])
        self.assertIsNone(rows[2])
        self.assertIsNone(rows[3])
        indexes = {row[1] for row in conn.execute("PRAGMA index_list('tasks')")}
        self.assertIn('idx_tasks_team_completed_at', indexes)
        conn.close()


class TaskArchiveApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        handle, cls.path = tempfile.mkstemp(suffix='.db')
        os.close(handle)
        cls.old_path = sqlite_backend.DB_PATH
        sqlite_backend.DB_PATH = cls.path
        db.init_db()
        conn = sqlite3.connect(cls.path)
        conn.execute("INSERT INTO teams (id, name) VALUES (1, 'Allowed'), (2, 'Denied')")
        conn.execute("INSERT INTO segments (id, name) VALUES (1, 'Segment')")
        conn.execute(
            '''INSERT INTO users (id, first_name, role, login, password_hash, is_assignee)
               VALUES (2, 'Limited', 'user', 'limited-archive', ?, 1),
                      (3, 'Editor', 'editor', 'editor-archive', ?, 1)''',
            (auth.hash_password('password123'), auth.hash_password('password123')),
        )
        conn.execute('INSERT INTO user_team_access (user_id, team_id) VALUES (2, 1), (3, 1)')
        conn.executescript('''
            INSERT INTO tasks (id, team_id, segment_id, name, task_status, completed_at) VALUES
                (10, 1, 1, 'Active alpha', 'new', NULL),
                (11, 1, 1, 'Recent alpha', 'done', datetime('now', '-29 days')),
                (12, 1, 1, 'Old alpha', 'done', datetime('now', '-31 days')),
                (13, 1, 1, 'Legacy alpha', 'cancelled', NULL),
                (14, 1, 1, 'Recent beta', 'cancelled', datetime('now', '-1 day')),
                (15, 1, 1, 'Restore admin', 'done', datetime('now', '-100 days')),
                (16, 1, 1, 'Restore editor', 'cancelled', datetime('now', '-101 days')),
                (17, 1, 1, 'Restore deleted', 'done', datetime('now', '-2 days')),
                (20, 2, 1, 'Denied task', 'done', datetime('now', '-1 day'));
            UPDATE tasks SET is_deleted = 1 WHERE id = 17;
            INSERT INTO assignments (id, task_id, date, status) VALUES (150, 15, '2026-07-01', 'new');
            INSERT INTO task_dependencies (task_id, depends_on_task_id) VALUES (15, 10);
        ''')
        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        sqlite_backend.DB_PATH = cls.old_path
        for suffix in ('', '-wal', '-shm'):
            try:
                os.remove(cls.path + suffix)
            except FileNotFoundError:
                pass

    def login(self, login='admin', password='q12345678'):
        client = TestClient(app)
        response = client.post('/login', data={'login': login, 'password': password})
        self.assertEqual(200, response.status_code)
        return client

    def test_status_updates_completion_timestamp_atomically(self):
        db.update_task_status(10, 'done')
        conn = sqlite3.connect(self.path)
        completed = conn.execute('SELECT completed_at FROM tasks WHERE id = 10').fetchone()[0]
        self.assertIsNotNone(completed)
        conn.execute("UPDATE tasks SET task_status = 'done', completed_at = '2026-01-01 00:00:00' WHERE id = 10")
        conn.commit()
        conn.close()

        db.update_task_status(10, 'cancelled')
        conn = sqlite3.connect(self.path)
        self.assertEqual('2026-01-01 00:00:00', conn.execute(
            'SELECT completed_at FROM tasks WHERE id = 10').fetchone()[0])
        conn.close()
        db.update_task_status(10, 'new')
        conn = sqlite3.connect(self.path)
        self.assertIsNone(conn.execute('SELECT completed_at FROM tasks WHERE id = 10').fetchone()[0])
        conn.close()

    def test_planning_list_includes_only_active_or_recent_terminal_tasks(self):
        with self.login() as client:
            active = client.get('/api/tasks/1').json()
            self.assertEqual([10], [task['id'] for task in active['tasks']])
            recent = client.get('/api/tasks/1', params={
                'include_recent_completed': 'true', 'search': 'alpha', 'offset': 0, 'limit': 10,
            }).json()
            self.assertEqual({10, 11}, {task['id'] for task in recent['tasks']})
            self.assertEqual(2, recent['total'])

    def test_direct_task_endpoint_ignores_age_but_enforces_access_and_missing(self):
        with self.login('limited-archive', 'password123') as client:
            response = client.get('/api/task/12')
            self.assertEqual(200, response.status_code)
            self.assertEqual(12, response.json()['id'])
            self.assertEqual(403, client.get('/api/task/20').status_code)
            self.assertEqual(404, client.get('/api/task/999').status_code)

    def test_archive_has_stable_pagination_search_period_and_legacy_rows(self):
        with self.login() as client:
            full = client.get('/api/tasks/1/archive', params={'limit': 2, 'offset': 0}).json()
            self.assertEqual(6, full['total'])
            self.assertEqual([14, 11], [task['id'] for task in full['tasks']])
            all_rows = client.get('/api/tasks/1/archive', params={'limit': 20}).json()
            self.assertEqual({11, 12, 13, 14, 15, 16}, {task['id'] for task in all_rows['tasks']})

            searched = client.get('/api/tasks/1/archive', params={'search': 'beta'}).json()
            self.assertEqual([14], [task['id'] for task in searched['tasks']])
            dated = client.get('/api/tasks/1/archive', params={'completed_from': '2000-01-01'}).json()
            self.assertEqual(5, dated['total'])
            self.assertNotIn(13, {task['id'] for task in dated['tasks']})

    def test_archive_validates_range_and_team_access(self):
        with self.login('limited-archive', 'password123') as client:
            self.assertEqual(422, client.get('/api/tasks/1/archive', params={
                'completed_from': '2026-07-02', 'completed_to': '2026-07-01'}).status_code)
            self.assertEqual(403, client.get('/api/tasks/2/archive').status_code)

    def test_restore_enforces_roles_is_one_shot_and_preserves_relations(self):
        with self.login('limited-archive', 'password123') as client:
            self.assertEqual(403, client.post('/api/task/15/restore').status_code)

        with self.login('editor-archive', 'password123') as client:
            response = client.post('/api/task/16/restore')
            self.assertEqual(200, response.status_code)
            self.assertEqual('new', client.get('/api/task/16').json()['task_status'])

        with self.login() as client:
            response = client.post('/api/task/15/restore')
            self.assertEqual(200, response.status_code)
            self.assertEqual(409, client.post('/api/task/15/restore').status_code)
            self.assertEqual(404, client.post('/api/task/17/restore').status_code)
            self.assertEqual(404, client.post('/api/task/999/restore').status_code)

        conn = sqlite3.connect(self.path)
        status, completed_at = conn.execute(
            'SELECT task_status, completed_at FROM tasks WHERE id = 15').fetchone()
        self.assertEqual(('new', None), (status, completed_at))
        self.assertEqual(1, conn.execute('SELECT COUNT(*) FROM assignments WHERE task_id = 15').fetchone()[0])
        self.assertEqual(1, conn.execute('SELECT COUNT(*) FROM task_dependencies WHERE task_id = 15').fetchone()[0])
        history = conn.execute(
            "SELECT old_value, new_value FROM task_history WHERE task_id = 15 AND field_name = 'task_status' "
            "ORDER BY id DESC LIMIT 1").fetchone()
        self.assertEqual(('done', 'new'), history)
        conn.close()


if __name__ == '__main__':
    unittest.main()
