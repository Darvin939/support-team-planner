import os
import sqlite3
import tempfile
import unittest

from fastapi.testclient import TestClient

import auth
import db
import db.sqlite as sqlite_backend
from support_planner import app


class TaskDependenciesRouterTest(unittest.TestCase):
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
               VALUES (2, 'Limited', 'user', 'limited', ?, 1)''',
            (auth.hash_password('password123'),),
        )
        conn.execute('INSERT INTO user_team_access (user_id, team_id) VALUES (2, 1)')
        conn.executemany(
            '''INSERT INTO tasks
               (id, team_id, segment_id, name, task_status, is_deleted)
               VALUES (?, ?, 1, ?, ?, ?)''',
            (
                (10, 1, 'Alpha task', 'new', 0),
                (11, 1, 'Beta task', 'new', 0),
                (12, 1, 'Done task', 'done', 0),
                (13, 1, 'Deleted task', 'new', 1),
                (20, 2, 'Denied task', 'new', 0),
            ),
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

    def setUp(self):
        conn = sqlite3.connect(self.path)
        conn.execute('DELETE FROM task_dependencies')
        conn.execute(
            'INSERT INTO task_dependencies (task_id, depends_on_task_id) VALUES (10, 11)',
        )
        conn.commit()
        conn.close()

    def login(self, login='admin', password='q12345678'):
        client = TestClient(app)
        response = client.post('/login', data={'login': login, 'password': password})
        self.assertEqual(200, response.status_code)
        return client

    def test_read_endpoints_preserve_graph_and_query_filters(self):
        with self.login() as client:
            deps = client.get('/api/tasks/1/deps', params={'task_ids': '10'})
            self.assertEqual(200, deps.status_code)
            self.assertEqual([(10, 11)], [(item['task_id'], item['dep_id']) for item in deps.json()])

            graph = client.get('/api/tasks/1/dependency-graph', params={'task_id': 10})
            self.assertEqual(200, graph.status_code)
            self.assertEqual({10, 11}, {node['id'] for node in graph.json()['nodes']})
            self.assertEqual([{'task_id': 10, 'dep_id': 11}], graph.json()['edges'])

            active = client.get(
                '/api/tasks/1/active-list',
                params={'search': 'missing', 'limit': 1, 'include_ids': '11'},
            )
            self.assertEqual(200, active.status_code)
            self.assertEqual([11], [task['id'] for task in active.json()])

    def test_team_and_both_task_access_checks_are_preserved(self):
        with self.login('limited', 'password123') as client:
            self.assertEqual(403, client.get('/api/tasks/2/deps').status_code)
            self.assertEqual(
                403,
                client.get('/api/tasks/1/dependency-graph', params={'task_id': 20}).status_code,
            )
            response = client.post(
                '/api/task-dependency',
                json={'task_id': 10, 'depends_on_task_id': 20},
            )
            self.assertEqual(403, response.status_code)

    def test_dependency_mutations_preserve_success_and_validation_errors(self):
        with self.login() as client:
            deleted = client.request(
                'DELETE',
                '/api/task-dependency',
                json={'task_id': 10, 'depends_on_task_id': 11},
            )
            self.assertEqual({'success': True}, deleted.json())

            added = client.post(
                '/api/task-dependency',
                json={'task_id': 10, 'depends_on_task_id': 11},
            )
            self.assertEqual({'success': True}, added.json())

            cases = (
                ({'task_id': 99, 'depends_on_task_id': 11}, 404, 'Команда не найдена'),
                ({'task_id': 10, 'depends_on_task_id': 20}, 400, 'Задачи принадлежат разным командам'),
                (
                    {'task_id': 12, 'depends_on_task_id': 11},
                    400,
                    'Нельзя редактировать завершённую или отменённую задачу',
                ),
                ({'task_id': 13, 'depends_on_task_id': 11}, 404, 'Задача не найдена'),
            )
            for payload, status, message in cases:
                with self.subTest(payload=payload):
                    response = client.post('/api/task-dependency', json=payload)
                    self.assertEqual(status, response.status_code)
                    self.assertEqual({'error': message}, response.json())

    def test_cycle_is_rejected_with_stable_error(self):
        with self.login() as client:
            response = client.post(
                '/api/task-dependency',
                json={'task_id': 11, 'depends_on_task_id': 10},
            )
            self.assertEqual(400, response.status_code)
            self.assertEqual({'error': 'Обнаружена циклическая зависимость'}, response.json())


if __name__ == '__main__':
    unittest.main()
