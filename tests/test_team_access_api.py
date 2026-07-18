import os
import sqlite3
import tempfile
import unittest

from fastapi.testclient import TestClient

import auth
import db
import db.sqlite as sqlite_backend
from support_planner import app


class TeamAccessApiTest(unittest.TestCase):
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
               VALUES (2, 'Limited', 'user', 'limited', ?, 1),
                      (3, 'Denied assignee', 'user', 'denied-assignee', ?, 1)''',
            (auth.hash_password('password123'), auth.hash_password('password123')),
        )
        conn.execute('INSERT INTO user_team_access (user_id, team_id) VALUES (2, 1), (3, 2)')
        conn.execute(
            "INSERT INTO tasks (id, team_id, segment_id, name) VALUES (10, 1, 1, 'Allowed task'), (20, 2, 1, 'Denied task')"
        )
        conn.execute("INSERT INTO assignments (id, task_id, date, status) VALUES (100, 1, '2026-07-18', 'new')".replace('(100, 1,', '(100, 10,'))
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

    def login(self, login, password):
        client = TestClient(app)
        response = client.post('/login', data={'login': login, 'password': password})
        self.assertEqual(200, response.status_code)
        return client

    def test_limited_user_sees_only_allowed_team(self):
        with self.login('limited', 'password123') as client:
            response = client.get('/api/teams')
            self.assertEqual(200, response.status_code)
            self.assertEqual([1], [team['id'] for team in response.json()])

    def test_admin_always_sees_all_teams(self):
        with self.login('admin', 'q12345678') as client:
            response = client.get('/api/teams')
            self.assertEqual({1, 2}, {team['id'] for team in response.json()})

    def test_direct_and_indirect_denied_team_requests_return_403(self):
        with self.login('limited', 'password123') as client:
            for path in (
                '/api/tasks/2', '/api/journal/2', '/api/task/20/history',
                '/api/active-assignments/0?team_ids=1,2',
            ):
                self.assertEqual(403, client.get(path).status_code, path)

    def test_assignees_are_filtered_and_direct_assignment_is_rejected(self):
        with self.login('limited', 'password123') as client:
            assignees = client.get('/api/teams/1/assignees')
            self.assertEqual(200, assignees.status_code)
            self.assertNotIn(3, {user['id'] for user in assignees.json()})
            response = client.post('/api/assignment', json={
                'task_id': 10, 'date': '2026-07-19', 'status': 'new', 'user_id': 3,
            })
            self.assertEqual(400, response.status_code)


if __name__ == '__main__':
    unittest.main()
