import os
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

import auth
import db
import db.connection as db_connection
import db.sqlite as sqlite_backend
from support_planner import app


class CompositeTransactionScopeTest(unittest.TestCase):
    def test_scope_defers_dao_commits_and_commits_once(self):
        conn = Mock()

        @db.with_db_connection()
        def first_step(current):
            self.assertIs(current, conn)

        @db.with_db_connection()
        def second_step(current):
            self.assertIs(current, conn)

        with patch.object(db_connection, 'get_db_connection', return_value=conn):
            with db.composite_transaction():
                first_step()
                second_step()

        conn.commit.assert_called_once_with()
        conn.rollback.assert_not_called()
        conn.close.assert_called_once_with()

    def test_scope_rolls_back_and_rejects_nesting(self):
        conn = Mock()

        @db.with_db_connection()
        def first_step(current):
            self.assertIs(current, conn)

        with patch.object(db_connection, 'get_db_connection', return_value=conn):
            with self.assertRaisesRegex(RuntimeError, 'boom'):
                with db.composite_transaction():
                    first_step()
                    raise RuntimeError('boom')

        conn.commit.assert_not_called()
        conn.rollback.assert_called_once_with()
        conn.close.assert_called_once_with()

        with patch.object(db_connection, 'get_db_connection', return_value=Mock()):
            with db.composite_transaction():
                with self.assertRaisesRegex(RuntimeError, 'Nested composite transactions'):
                    with db.composite_transaction():
                        pass

    def test_single_dao_call_keeps_immediate_commit(self):
        conn = Mock()

        @db.with_db_connection()
        def single_step(current):
            self.assertIs(current, conn)

        with patch.object(db_connection, 'get_db_connection', return_value=conn):
            single_step()

        conn.commit.assert_called_once_with()
        conn.close.assert_called_once_with()


class CompositeTransactionApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        handle, cls.path = tempfile.mkstemp(suffix='.db')
        os.close(handle)
        cls.old_path = sqlite_backend.DB_PATH
        sqlite_backend.DB_PATH = cls.path
        db.init_db()

        conn = sqlite3.connect(cls.path)
        conn.execute("INSERT INTO teams (id, name) VALUES (1, 'Existing team')")
        conn.execute("INSERT INTO segments (id, name) VALUES (1, 'Segment')")
        conn.execute(
            '''INSERT INTO users (id, first_name, role, login, password_hash, is_assignee)
               VALUES (2, 'Editor', 'editor', 'transaction-editor', ?, 1)''',
            (auth.hash_password('password123'),),
        )
        conn.execute('INSERT INTO user_team_access (user_id, team_id) VALUES (2, 1)')
        conn.execute(
            '''INSERT INTO tasks
               (id, team_id, segment_id, name, description, criticality, priority, task_status)
               VALUES (10, 1, 1, 'Original task', 'Original description', 'medium', 1000, 'new'),
                      (11, 1, 1, 'Dependency', NULL, 'low', 2000, 'new')'''
        )
        conn.execute('INSERT INTO task_dependencies (task_id, depends_on_task_id) VALUES (10, 11)')
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
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post('/login', data={'login': login, 'password': password})
        self.assertEqual(200, response.status_code)
        return client

    def test_task_creation_rolls_back_when_dependency_write_fails(self):
        with self.login() as client, patch.object(
            db, 'set_task_dependencies', side_effect=RuntimeError('dependency write failed')
        ):
            response = client.post('/api/task', json={
                'team_id': 1,
                'name': 'Rolled back task',
                'criticality': 'high',
                'segment_id': 1,
                'dependency_ids': [],
            })
            self.assertEqual(500, response.status_code)

        conn = sqlite3.connect(self.path)
        self.assertEqual(0, conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE name = 'Rolled back task'"
        ).fetchone()[0])
        self.assertEqual(0, conn.execute(
            "SELECT COUNT(*) FROM task_history th "
            "JOIN tasks t ON t.id = th.task_id WHERE t.name = 'Rolled back task'"
        ).fetchone()[0])
        conn.close()

    def test_task_edit_rolls_back_data_history_and_dependencies(self):
        with self.login() as client, patch.object(
            db, 'set_task_dependencies', side_effect=RuntimeError('dependency write failed')
        ):
            response = client.post('/api/task', json={
                'task_id': 10,
                'team_id': 1,
                'name': 'Changed task',
                'description': 'Changed description',
                'criticality': 'high',
                'segment_id': 1,
                'dependency_ids': [],
            })
            self.assertEqual(500, response.status_code)

        conn = sqlite3.connect(self.path)
        task = conn.execute(
            'SELECT name, description, criticality FROM tasks WHERE id = 10'
        ).fetchone()
        self.assertEqual(('Original task', 'Original description', 'medium'), task)
        self.assertEqual([(11,)], conn.execute(
            'SELECT depends_on_task_id FROM task_dependencies WHERE task_id = 10'
        ).fetchall())
        self.assertEqual(0, conn.execute(
            'SELECT COUNT(*) FROM task_history WHERE task_id = 10'
        ).fetchone()[0])
        conn.close()

    def test_team_creation_rolls_back_templates_when_access_grant_fails(self):
        with self.login('transaction-editor', 'password123') as client, patch.object(
            db, 'grant_team_access_if_restricted', side_effect=RuntimeError('access grant failed')
        ):
            response = client.post('/api/teams', json={'name': 'Rolled back team', 'template_ids': []})
            self.assertEqual(500, response.status_code)

        conn = sqlite3.connect(self.path)
        self.assertEqual(0, conn.execute(
            "SELECT COUNT(*) FROM teams WHERE name = 'Rolled back team'"
        ).fetchone()[0])
        self.assertEqual(0, conn.execute(
            '''SELECT COUNT(*) FROM team_templates tt
               JOIN teams t ON t.id = tt.team_id WHERE t.name = 'Rolled back team' '''
        ).fetchone()[0])
        conn.close()


if __name__ == '__main__':
    unittest.main()
