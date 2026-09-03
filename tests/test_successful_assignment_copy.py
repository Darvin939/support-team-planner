import os
import sqlite3
import tempfile
import unittest

from fastapi.testclient import TestClient

import auth
import db
import db.sqlite as sqlite_backend
from support_planner import app


class SuccessfulAssignmentCopyTest(unittest.TestCase):
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
               VALUES (2, 'Limited', 'user', 'limited-copy', ?, 1)''',
            (auth.hash_password('password123'),),
        )
        conn.execute('INSERT INTO user_team_access (user_id, team_id) VALUES (2, 1)')
        conn.execute(
            "INSERT INTO tasks (id, team_id, segment_id, name) VALUES "
            "(10, 1, 1, 'Allowed task'), (11, 1, 1, 'Other allowed task'), (20, 2, 1, 'Denied task')"
        )
        conn.executemany(
            '''INSERT INTO assignments (id, task_id, date, block, status, is_deleted)
               VALUES (?, ?, ?, ?, ?, ?)''',
            [
                (100, 10, '2025-01-02', 'Old', 'success', 0),
                (101, 10, '2026-12-31', 'New', 'success', 0),
                (102, 10, '2026-06-01', 'Ignored status', 'planned', 0),
                (103, 10, '2026-06-02', 'Deleted', 'success', 1),
                (104, 11, '2026-06-03', 'Other task', 'success', 0),
                (200, 20, '2026-06-04', 'Denied', 'success', 0),
            ],
        )
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

    def login(self, login='limited-copy', password='password123'):
        client = TestClient(app)
        response = client.post('/login', data={'login': login, 'password': password})
        self.assertEqual(200, response.status_code)
        return client

    def test_dao_returns_only_successful_undeleted_task_history_in_date_order(self):
        rows = db.get_successful_assignments_by_task(10)

        self.assertEqual([100, 101], [row['id'] for row in rows])
        self.assertEqual(['2025-01-02', '2026-12-31'], [row['date'] for row in rows])

    def test_endpoint_returns_full_history_without_date_range(self):
        with self.login() as client:
            response = client.get('/api/assignments/1/task/10/successful-history')

        self.assertEqual(200, response.status_code)
        self.assertEqual([100, 101], [item['id'] for item in response.json()])

    def test_endpoint_checks_team_access_and_task_membership(self):
        with self.login() as client:
            self.assertEqual(403, client.get('/api/assignments/2/task/20/successful-history').status_code)
            self.assertEqual(403, client.get('/api/assignments/1/task/20/successful-history').status_code)
            self.assertEqual(404, client.get('/api/assignments/1/task/999/successful-history').status_code)
        with self.login('admin', 'q12345678') as client:
            self.assertEqual(404, client.get('/api/assignments/1/task/20/successful-history').status_code)


if __name__ == '__main__':
    unittest.main()
