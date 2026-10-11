import os
import sqlite3
import tempfile
import unittest

from fastapi.testclient import TestClient

import backend.db.sqlite as sqlite_backend
from backend import auth, db
from backend.application import app


class StatisticsCalendarCountsTest(unittest.TestCase):
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
               VALUES (2, 'Limited', 'user', 'limited-counts', ?, 1)''',
            (auth.hash_password('password123'),),
        )
        conn.execute('INSERT INTO user_team_access (user_id, team_id) VALUES (2, 1)')
        conn.execute(
            "INSERT INTO tasks (id, team_id, segment_id, name, task_status, is_deleted) VALUES "
            "(10, 1, 1, 'Active one', 'new', 0), (13, 1, 1, 'Active two', 'new', 0), "
            "(11, 1, 1, 'Done', 'done', 0), (12, 1, 1, 'Deleted', 'new', 1), "
            "(20, 2, 1, 'Denied', 'new', 0)"
        )
        conn.executemany(
            'INSERT INTO assignments (id, task_id, date, status, is_deleted) VALUES (?, ?, ?, ?, ?)',
            [
                (100, 10, '2026-07-18', 'new', 0),
                (101, 13, '2026-07-18', 'planned', 0),
                (102, 10, '2026-07-19', 'success', 0),
                (103, 10, '2026-07-19', 'new', 1),
                (104, 11, '2026-07-19', 'new', 0),
                (105, 12, '2026-07-19', 'new', 0),
                (200, 20, '2026-07-18', 'new', 0),
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

    def login(self):
        client = TestClient(app)
        response = client.post('/login', data={'login': 'limited-counts', 'password': 'password123'})
        self.assertEqual(200, response.status_code)
        return client

    def test_dao_groups_only_active_assignments_and_honors_bounds_and_teams(self):
        rows = db.get_active_assignment_counts_by_date(
            0, '2026-07-18', '2026-07-18', team_ids=[1],
        )
        self.assertEqual([('2026-07-18', 2)], [(row['date'], row['count']) for row in rows])

        denied_rows = db.get_active_assignment_counts_by_date(
            0, '2026-07-18', '2026-07-19', team_ids=[2],
        )
        self.assertEqual([('2026-07-18', 1)], [(row['date'], row['count']) for row in denied_rows])

    def test_api_returns_counts_for_effective_team_scope(self):
        with self.login() as client:
            response = client.get('/api/active-assignment-counts/0', params={
                'start_date': '2026-07-18', 'end_date': '2026-07-19',
            })
        self.assertEqual(200, response.status_code)
        self.assertEqual([{'date': '2026-07-18', 'count': 2}], response.json())

    def test_api_validates_dates_and_team_access(self):
        with self.login() as client:
            for params in (
                {},
                {'start_date': 'not-a-date', 'end_date': '2026-07-19'},
                {'start_date': '2026-07-20', 'end_date': '2026-07-19'},
            ):
                with self.subTest(params=params):
                    self.assertEqual(422, client.get('/api/active-assignment-counts/0', params=params).status_code)
            denied = client.get('/api/active-assignment-counts/0', params={
                'start_date': '2026-07-18', 'end_date': '2026-07-19', 'team_ids': '1,2',
            })
            self.assertEqual(403, denied.status_code)


if __name__ == '__main__':
    unittest.main()
