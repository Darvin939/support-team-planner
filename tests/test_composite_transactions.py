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
        conn.execute(
            '''INSERT INTO users (id, first_name, role, login, password_hash, is_assignee)
               VALUES (3, 'User', 'user', 'transaction-user', ?, 1)''',
            (auth.hash_password('password123'),),
        )
        conn.execute('INSERT INTO user_team_access (user_id, team_id) VALUES (2, 1)')
        conn.execute('INSERT INTO user_team_access (user_id, team_id) VALUES (3, 1)')
        conn.execute(
            '''INSERT INTO tasks
               (id, team_id, segment_id, name, description, criticality, priority, task_status)
               VALUES (10, 1, 1, 'Original task', 'Original description', 'medium', 1000, 'new'),
                      (11, 1, 1, 'Dependency', NULL, 'low', 2000, 'new')'''
        )
        conn.execute('INSERT INTO task_dependencies (task_id, depends_on_task_id) VALUES (10, 11)')
        conn.execute("INSERT INTO blocks (id, name) VALUES (1, 'Backend'), (2, 'Frontend'), (3, 'Docs')")
        conn.execute(
            "INSERT INTO block_templates (id, name, segment_id) VALUES "
            "(1, 'Delivery', 1), (2, 'Docs only', 1), (3, 'Empty', 1)"
        )
        conn.execute(
            'INSERT INTO template_blocks (template_id, block_id, schedule_offset) VALUES (1, 1, 0), (1, 2, 1), (2, 3, 0)'
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
                'instruction_url': 'https://example.test/changed',
                'criticality': 'high',
                'segment_id': 1,
                'dependency_ids': [],
            })
            self.assertEqual(500, response.status_code)

        conn = sqlite3.connect(self.path)
        task = conn.execute(
            'SELECT name, description, instruction_url, criticality FROM tasks WHERE id = 10'
        ).fetchone()
        self.assertEqual(('Original task', 'Original description', None, 'medium'), task)
        self.assertEqual([(11,)], conn.execute(
            'SELECT depends_on_task_id FROM task_dependencies WHERE task_id = 10'
        ).fetchall())
        self.assertEqual(0, conn.execute(
            'SELECT COUNT(*) FROM task_history WHERE task_id = 10'
        ).fetchone()[0])
        conn.close()

    def test_task_instruction_url_create_update_clear_and_history(self):
        with self.login() as client:
            created = client.post('/api/task', json={
                'team_id': 1,
                'name': 'Instruction task',
                'description': 'Description with https://example.test/inside-description',
                'instruction_url': 'https://example.test/new-instruction',
                'criticality': 'low',
                'segment_id': 1,
                'dependency_ids': [],
            })
            self.assertEqual(200, created.status_code)
            created_id = created.json()['id']
            self.assertEqual(
                'https://example.test/new-instruction',
                client.get(f'/api/task/{created_id}').json()['instruction_url'],
            )

        conn = sqlite3.connect(self.path)
        snapshot = conn.execute(
            "SELECT new_value FROM task_history WHERE task_id = ? AND action = 'create'",
            (created_id,),
        ).fetchone()[0]
        self.assertIn('"instruction_url": "https://example.test/new-instruction"', snapshot)
        conn.execute('DELETE FROM task_history WHERE task_id = ?', (created_id,))
        conn.execute('DELETE FROM tasks WHERE id = ?', (created_id,))
        conn.commit()
        conn.close()

        payload = {
            'task_id': 10,
            'team_id': 1,
            'name': 'Original task',
            'description': 'Original description',
            'instruction_url': '  https://example.test/instructions/10  ',
            'criticality': 'medium',
            'segment_id': 1,
            'dependency_ids': [11],
        }
        with self.login() as client:
            response = client.post('/api/task', json=payload)
            self.assertEqual(200, response.status_code)
            self.assertEqual(
                'https://example.test/instructions/10',
                client.get('/api/task/10').json()['instruction_url'],
            )
            self.assertEqual(
                'https://example.test/instructions/10',
                client.get('/api/tasks/1').json()['tasks'][0]['instruction_url'],
            )

            payload['instruction_url'] = '   '
            response = client.post('/api/task', json=payload)
            self.assertEqual(200, response.status_code)
            self.assertIsNone(client.get('/api/task/10').json()['instruction_url'])

        conn = sqlite3.connect(self.path)
        history = conn.execute(
            "SELECT old_value, new_value FROM task_history "
            "WHERE task_id = 10 AND field_name = 'instruction_url' ORDER BY id"
        ).fetchall()
        self.assertEqual(
            [(None, 'https://example.test/instructions/10'), ('https://example.test/instructions/10', None)],
            history,
        )
        conn.execute("DELETE FROM task_history WHERE task_id = 10 AND field_name = 'instruction_url'")
        conn.commit()
        conn.close()

    def test_task_instruction_url_validation_does_not_change_task_or_dependencies(self):
        payload = {
            'task_id': 10,
            'team_id': 1,
            'name': 'Should not be saved',
            'description': 'Should not be saved',
            'criticality': 'high',
            'segment_id': 1,
            'dependency_ids': [],
        }
        invalid_urls = ('relative/path', 'https:///missing-host', 'javascript:alert(1)', 'https://x.test/' + 'a' * 2040)
        with self.login() as client:
            for invalid_url in invalid_urls:
                response = client.post('/api/task', json={**payload, 'instruction_url': invalid_url})
                self.assertEqual(400, response.status_code)
                self.assertEqual({'error': 'Некорректная ссылка на инструкцию'}, response.json())

        conn = sqlite3.connect(self.path)
        self.assertEqual(
            ('Original task', 'Original description', None, 'medium'),
            conn.execute(
                'SELECT name, description, instruction_url, criticality FROM tasks WHERE id = 10'
            ).fetchone(),
        )
        self.assertEqual(
            [(11,)],
            conn.execute(
                'SELECT depends_on_task_id FROM task_dependencies WHERE task_id = 10'
            ).fetchall(),
        )
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

    def test_bulk_assignment_upsert_rolls_back_entire_batch(self):
        original = db.create_or_update_assignment
        calls = 0

        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError('second assignment failed')
            return original(*args, **kwargs)

        payload = {'assignments': [
            {'task_id': 10, 'date': '2026-08-01', 'block': 'A', 'status': 'new'},
            {'task_id': 10, 'date': '2026-08-02', 'block': 'B', 'status': 'new'},
        ]}
        with self.login() as client, patch.object(db, 'create_or_update_assignment', side_effect=fail_second):
            response = client.post('/api/assignments/bulk', json=payload)
            self.assertEqual(500, response.status_code)

        conn = sqlite3.connect(self.path)
        self.assertEqual(0, conn.execute(
            "SELECT COUNT(*) FROM assignments WHERE date IN ('2026-08-01', '2026-08-02')"
        ).fetchone()[0])
        conn.close()

    def test_bulk_assignment_upsert_saves_complete_batch(self):
        payload = {'assignments': [
            {'task_id': 10, 'date': '2026-08-03', 'block': 'A', 'status': 'new'},
            {'task_id': 10, 'date': '2026-08-04', 'block': 'B', 'status': 'new'},
        ]}
        with self.login() as client:
            response = client.post('/api/assignments/bulk', json=payload)
            self.assertEqual(200, response.status_code)
            self.assertEqual({'success': True, 'saved': 2}, response.json())

        conn = sqlite3.connect(self.path)
        self.assertEqual(2, conn.execute(
            "SELECT COUNT(*) FROM assignments WHERE date IN ('2026-08-03', '2026-08-04')"
        ).fetchone()[0])
        conn.execute("DELETE FROM assignments WHERE date IN ('2026-08-03', '2026-08-04')")
        conn.commit()
        conn.close()

    def test_bulk_auto_assignment_saves_replaces_and_rolls_back_template(self):
        first_payload = {
            'template_id': 1,
            'assignments': [
                {'task_id': 10, 'date': '2026-08-20', 'block': 'Backend', 'status': 'new'},
                {'task_id': 10, 'date': '2026-08-21', 'block': 'Frontend', 'status': 'new'},
            ],
        }
        with self.login('transaction-editor', 'password123') as client:
            response = client.post('/api/assignments/bulk', json=first_payload)
        self.assertEqual(200, response.status_code)

        conn = sqlite3.connect(self.path)
        self.assertEqual(1, conn.execute(
            'SELECT completion_template_id FROM tasks WHERE id = 10'
        ).fetchone()[0])
        conn.close()

        with self.login('transaction-editor', 'password123') as client:
            response = client.post('/api/assignments/bulk', json={
                'template_id': 2,
                'assignments': [{'task_id': 10, 'date': '2026-08-22', 'block': 'Docs', 'status': 'new'}],
            })
        self.assertEqual(200, response.status_code)

        original = db.create_or_update_assignment
        calls = 0

        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError('second assignment failed')
            return original(*args, **kwargs)

        rollback_payload = {
            'template_id': 1,
            'assignments': [
                {'task_id': 10, 'date': '2026-08-23', 'block': 'Backend', 'status': 'new'},
                {'task_id': 10, 'date': '2026-08-24', 'block': 'Frontend', 'status': 'new'},
            ],
        }
        with self.login('transaction-editor', 'password123') as client, patch.object(
            db, 'create_or_update_assignment', side_effect=fail_second,
        ):
            response = client.post('/api/assignments/bulk', json=rollback_payload)
        self.assertEqual(500, response.status_code)

        conn = sqlite3.connect(self.path)
        self.assertEqual(2, conn.execute(
            'SELECT completion_template_id FROM tasks WHERE id = 10'
        ).fetchone()[0])
        self.assertEqual(0, conn.execute(
            "SELECT COUNT(*) FROM assignments WHERE date IN ('2026-08-23', '2026-08-24')"
        ).fetchone()[0])
        conn.execute("DELETE FROM assignments WHERE date BETWEEN '2026-08-20' AND '2026-08-24'")
        conn.execute('UPDATE tasks SET completion_template_id = NULL WHERE id = 10')
        conn.commit()
        conn.close()

    def test_completion_readiness_matrix_and_save_suggestion(self):
        conn = sqlite3.connect(self.path)
        conn.execute('UPDATE tasks SET completion_template_id = 1, task_status = \'new\' WHERE id = 10')
        conn.execute(
            "INSERT INTO assignments (id, task_id, date, block, status) VALUES "
            "(210, 10, '2026-08-25', 'Backend', 'success'), "
            "(211, 10, '2026-08-26', 'Frontend', 'planned'), "
            "(212, 10, '2026-08-27', 'Unrelated', 'new')"
        )
        conn.commit()
        conn.close()

        self.assertIsNone(db.get_task_completion_suggestion(10))

        with self.login('transaction-editor', 'password123') as client:
            response = client.post('/api/assignment', json={
                'assignment_id': 211,
                'task_id': 10,
                'date': '2026-08-26',
                'block': 'Frontend',
                'status': 'success',
            })
        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {'task_id': 10, 'task_name': 'Original task'},
            response.json()['task_completion_suggestion'],
        )
        self.assertIsNotNone(db.get_task_completion_suggestion(10))

        conn = sqlite3.connect(self.path)
        conn.execute('DELETE FROM assignments WHERE id = 210')
        conn.commit()
        conn.close()
        self.assertIsNone(db.get_task_completion_suggestion(10))

        conn = sqlite3.connect(self.path)
        conn.execute('UPDATE tasks SET completion_template_id = 3 WHERE id = 10')
        conn.commit()
        conn.close()
        self.assertIsNone(db.get_task_completion_suggestion(10))

        conn = sqlite3.connect(self.path)
        conn.execute("INSERT INTO assignments (id, task_id, date, block, status) VALUES (210, 10, '2026-08-25', 'Backend', 'success')")
        conn.execute('UPDATE tasks SET completion_template_id = NULL WHERE id = 10')
        conn.commit()
        conn.close()
        self.assertIsNone(db.get_task_completion_suggestion(10))

        conn = sqlite3.connect(self.path)
        conn.execute('UPDATE tasks SET completion_template_id = 2 WHERE id = 10')
        conn.commit()
        conn.close()
        self.assertIsNone(db.get_task_completion_suggestion(10))

        conn = sqlite3.connect(self.path)
        conn.execute('DELETE FROM assignments WHERE id IN (210, 211, 212)')
        conn.execute('UPDATE tasks SET completion_template_id = NULL WHERE id = 10')
        conn.commit()
        conn.close()

    def test_user_assignment_status_policy_for_single_upsert(self):
        with self.login('transaction-user', 'password123') as client:
            created = client.post('/api/assignment', json={
                'task_id': 10, 'date': '2026-08-10', 'block': 'Initial', 'status': 'new',
            })
            forbidden_create = client.post('/api/assignment', json={
                'task_id': 10, 'date': '2026-08-11', 'status': 'planned',
            })

        self.assertEqual(200, created.status_code)
        self.assertEqual(403, forbidden_create.status_code)

        conn = sqlite3.connect(self.path)
        assignment_id = conn.execute(
            "SELECT id FROM assignments WHERE task_id = 10 AND date = '2026-08-10'"
        ).fetchone()[0]
        conn.execute("UPDATE assignments SET status = 'planned' WHERE id = ?", (assignment_id,))
        conn.commit()
        conn.close()

        with self.login('transaction-user', 'password123') as client:
            unchanged_status = client.post('/api/assignment', json={
                'assignment_id': assignment_id, 'task_id': 10, 'date': '2026-08-10',
                'block': 'Changed', 'status': 'planned',
            })
            changed_status = client.post('/api/assignment', json={
                'assignment_id': assignment_id, 'task_id': 10, 'date': '2026-08-10',
                'block': 'Changed again', 'status': 'success',
            })

        self.assertEqual(200, unchanged_status.status_code)
        self.assertEqual(403, changed_status.status_code)
        conn = sqlite3.connect(self.path)
        self.assertEqual(
            ('Changed', 'planned'),
            conn.execute('SELECT block, status FROM assignments WHERE id = ?', (assignment_id,)).fetchone(),
        )
        self.assertEqual(0, conn.execute(
            "SELECT COUNT(*) FROM assignments WHERE task_id = 10 AND date = '2026-08-11'"
        ).fetchone()[0])
        conn.execute('DELETE FROM assignments WHERE id = ?', (assignment_id,))
        conn.commit()
        conn.close()

    def test_user_bulk_status_change_rolls_back_entire_upsert(self):
        conn = sqlite3.connect(self.path)
        conn.execute(
            "INSERT INTO assignments (id, task_id, date, block, status) "
            "VALUES (204, 10, '2026-08-12', 'Original', 'new')"
        )
        conn.commit()
        conn.close()

        payload = {'assignments': [
            {'task_id': 10, 'date': '2026-08-13', 'block': 'Would be created', 'status': 'new'},
            {'assignment_id': 204, 'task_id': 10, 'date': '2026-08-12', 'block': 'Forbidden', 'status': 'planned'},
        ]}
        with self.login('transaction-user', 'password123') as client:
            response = client.post('/api/assignments/bulk', json=payload)

        self.assertEqual(403, response.status_code)
        conn = sqlite3.connect(self.path)
        self.assertEqual(
            ('Original', 'new'),
            conn.execute('SELECT block, status FROM assignments WHERE id = 204').fetchone(),
        )
        self.assertEqual(0, conn.execute(
            "SELECT COUNT(*) FROM assignments WHERE task_id = 10 AND date = '2026-08-13'"
        ).fetchone()[0])
        conn.execute('DELETE FROM assignments WHERE id = 204')
        conn.commit()
        conn.close()

    def test_editor_and_admin_can_change_assignment_status(self):
        conn = sqlite3.connect(self.path)
        conn.execute(
            "INSERT INTO assignments (id, task_id, date, status) VALUES (205, 10, '2026-08-14', 'new')"
        )
        conn.commit()
        conn.close()

        for login, password, target_status in (
            ('transaction-editor', 'password123', 'planned'),
            ('admin', 'q12345678', 'success'),
        ):
            with self.login(login, password) as client:
                response = client.post('/api/assignment', json={
                    'assignment_id': 205, 'task_id': 10, 'date': '2026-08-14', 'status': target_status,
                })
            self.assertEqual(200, response.status_code)

        conn = sqlite3.connect(self.path)
        self.assertEqual('success', conn.execute(
            'SELECT status FROM assignments WHERE id = 205'
        ).fetchone()[0])
        conn.execute('DELETE FROM assignments WHERE id = 205')
        conn.commit()
        conn.close()

    def test_bulk_assignment_delete_is_atomic_when_an_item_is_missing(self):
        conn = sqlite3.connect(self.path)
        conn.execute(
            "INSERT INTO assignments (id, task_id, date, status, is_deleted) VALUES (201, 10, '2026-08-05', 'new', 0)"
        )
        conn.commit()
        conn.close()

        with self.login() as client:
            response = client.post('/api/assignments/bulk-delete', json={'assignment_ids': [201, 999999]})
            self.assertEqual(404, response.status_code)

        conn = sqlite3.connect(self.path)
        self.assertEqual(0, conn.execute('SELECT is_deleted FROM assignments WHERE id = 201').fetchone()[0])
        conn.execute('DELETE FROM assignments WHERE id = 201')
        conn.commit()
        conn.close()

    def test_bulk_assignment_delete_enforces_user_role_and_deletes_complete_batch(self):
        conn = sqlite3.connect(self.path)
        conn.execute(
            "INSERT INTO assignments (id, task_id, date, status, is_deleted) VALUES (202, 10, '2026-08-06', 'planned', 0)"
        )
        conn.execute(
            "INSERT INTO assignments (id, task_id, date, status, is_deleted) VALUES (203, 10, '2026-08-07', 'new', 0)"
        )
        conn.commit()
        conn.close()

        with self.login('transaction-user', 'password123') as client:
            response = client.post('/api/assignments/bulk-delete', json={'assignment_ids': [202, 203]})
            self.assertEqual(403, response.status_code)

        with self.login() as client:
            response = client.post('/api/assignments/bulk-delete', json={'assignment_ids': [202, 203]})
            self.assertEqual(200, response.status_code)
            self.assertEqual({'success': True, 'deleted': 2}, response.json())

        conn = sqlite3.connect(self.path)
        self.assertEqual([(1,), (1,)], conn.execute(
            'SELECT is_deleted FROM assignments WHERE id IN (202, 203) ORDER BY id'
        ).fetchall())
        conn.execute('DELETE FROM assignments WHERE id IN (202, 203)')
        conn.commit()
        conn.close()


    def test_task_psi_can_be_changed_by_user_but_not_on_terminal_task(self):
        payload = {
            'task_id': 10, 'team_id': 1, 'name': 'Original task',
            'description': 'Original description', 'criticality': 'medium',
            'segment_id': 1, 'psi_status': 'passed',
        }
        with self.login('transaction-user', 'password123') as client:
            response = client.post('/api/task', json=payload)
            self.assertEqual(200, response.status_code)

        conn = sqlite3.connect(self.path)
        self.assertEqual('passed', conn.execute('SELECT psi_status FROM tasks WHERE id = 10').fetchone()[0])
        history = conn.execute(
            "SELECT old_value, new_value, changed_by_user_id FROM task_history "
            "WHERE task_id = 10 AND field_name = 'psi_status' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        self.assertEqual(('not_required', 'passed', 3), history)
        conn.execute("UPDATE tasks SET task_status = 'done' WHERE id = 10")
        conn.commit()
        conn.close()

        payload['psi_status'] = 'not_required'
        with self.login('transaction-user', 'password123') as client:
            response = client.post('/api/task', json=payload)
            self.assertEqual(400, response.status_code)

        conn = sqlite3.connect(self.path)
        conn.execute("UPDATE tasks SET task_status = 'new', psi_status = 'not_required' WHERE id = 10")
        conn.commit()
        conn.close()

    def test_task_psi_result_endpoint_transitions_audits_and_validates(self):
        conn = sqlite3.connect(self.path)
        conn.execute("UPDATE tasks SET task_status = 'new', psi_status = 'required' WHERE id = 10")
        conn.execute("DELETE FROM assignments WHERE task_id = 10")
        conn.execute("DELETE FROM task_history WHERE task_id = 10 AND field_name = 'psi_status'")
        conn.commit()
        conn.close()

        with self.login('transaction-user', 'password123') as client:
            response = client.patch('/api/tasks/10/psi-status', json={'psi_status': 'passed'})
            self.assertEqual(200, response.status_code)

        conn = sqlite3.connect(self.path)
        self.assertEqual('passed', conn.execute('SELECT psi_status FROM tasks WHERE id = 10').fetchone()[0])
        self.assertEqual(
            ('required', 'passed', 3),
            conn.execute(
                "SELECT old_value, new_value, changed_by_user_id FROM task_history "
                "WHERE task_id = 10 AND field_name = 'psi_status' ORDER BY id DESC LIMIT 1"
            ).fetchone(),
        )
        conn.close()

        with self.login('transaction-user', 'password123') as client:
            response = client.patch('/api/tasks/10/psi-status', json={'psi_status': 'required'})
            self.assertEqual(200, response.status_code)

        conn = sqlite3.connect(self.path)
        conn.execute("INSERT INTO assignments (id, task_id, date, status) VALUES (221, 10, '2026-09-21', 'planned')")
        conn.execute("UPDATE tasks SET psi_status = 'passed' WHERE id = 10")
        conn.commit()
        conn.close()

        with self.login('transaction-user', 'password123') as client:
            response = client.patch('/api/tasks/10/psi-status', json={'psi_status': 'required'})
            self.assertEqual(400, response.status_code)
            self.assertIn('активные назначения', response.json()['error'])

        conn = sqlite3.connect(self.path)
        conn.execute("DELETE FROM assignments WHERE id = 221")
        conn.execute("UPDATE tasks SET task_status = 'done', psi_status = 'required' WHERE id = 10")
        conn.commit()
        conn.close()

        with self.login('transaction-user', 'password123') as client:
            response = client.patch('/api/tasks/10/psi-status', json={'psi_status': 'passed'})
            self.assertEqual(400, response.status_code)

        conn = sqlite3.connect(self.path)
        conn.execute("UPDATE tasks SET task_status = 'new', psi_status = 'not_required' WHERE id = 10")
        conn.execute("DELETE FROM task_history WHERE task_id = 10 AND field_name = 'psi_status'")
        conn.commit()
        conn.close()

    def test_required_psi_allows_only_new_planning_and_bulk_is_atomic(self):
        conn = sqlite3.connect(self.path)
        conn.execute("UPDATE tasks SET psi_status = 'required' WHERE id = 10")
        conn.commit()
        conn.close()

        assignment = {'task_id': 10, 'date': '2026-09-10', 'block': 'Backend', 'status': 'new'}
        with self.login('transaction-user', 'password123') as client:
            self.assertEqual(200, client.post('/api/assignment', json=assignment).status_code)
            self.assertEqual(400, client.post('/api/assignment', json={
                **assignment, 'date': '2026-09-13', 'status': 'planned',
            }).status_code)
            response = client.post('/api/assignments/bulk', json={'assignments': [
                {'task_id': 11, 'date': '2026-09-11', 'block': 'Docs', 'status': 'new'},
                {'task_id': 10, 'date': '2026-09-12', 'block': 'Frontend', 'status': 'planned'},
            ]})
            self.assertEqual(400, response.status_code)
            response = client.post('/api/assignments/bulk', json={'assignments': [
                {'task_id': 11, 'date': '2026-09-11', 'block': 'Docs', 'status': 'new'},
                {'task_id': 10, 'date': '2026-09-16', 'block': 'Frontend', 'status': 'new'},
            ]})
            self.assertEqual(200, response.status_code)

        conn = sqlite3.connect(self.path)
        self.assertEqual(3, conn.execute(
            "SELECT COUNT(*) FROM assignments WHERE date IN ('2026-09-10', '2026-09-11', '2026-09-12', '2026-09-13', '2026-09-16')"
        ).fetchone()[0])
        assignment_id = conn.execute("SELECT id FROM assignments WHERE task_id = 10 AND date = '2026-09-10'").fetchone()[0]
        conn.commit()
        conn.close()
        with self.login() as client:
            self.assertEqual(200, client.post('/api/assignments/bulk-reschedule', json={
                'moves': [{'assignment_id': assignment_id, 'new_date': '2026-09-12'}],
            }).status_code)
            updated = dict(assignment, assignment_id=assignment_id, date='2026-09-12', status='planned')
            self.assertEqual(400, client.post('/api/assignment', json=updated).status_code)
            self.assertEqual(200, client.delete(f'/api/assignment/{assignment_id}').status_code)

        conn = sqlite3.connect(self.path)
        conn.execute(
            "INSERT INTO assignments (id, task_id, date, block, status) VALUES "
            "(9222, 10, '2026-09-14', 'Legacy', 'planned')"
        )
        conn.commit()
        conn.close()
        legacy = {
            'assignment_id': 9222, 'task_id': 10, 'date': '2026-09-14', 'block': 'Legacy',
            'status': 'planned', 'comment': 'allowed', 'time_spent': '01:00',
        }
        with self.login() as client:
            self.assertEqual(200, client.post('/api/assignment', json=legacy).status_code)
            self.assertEqual(400, client.post('/api/assignment', json={**legacy, 'date': '2026-09-15'}).status_code)
            self.assertEqual(400, client.post('/api/assignment', json={**legacy, 'status': 'new'}).status_code)
            self.assertEqual(400, client.post('/api/assignments/bulk-reschedule', json={
                'moves': [{'assignment_id': 9222, 'new_date': '2026-09-15'}],
            }).status_code)
            self.assertEqual(200, client.delete('/api/assignment/9222').status_code)

        conn = sqlite3.connect(self.path)
        conn.execute("UPDATE tasks SET psi_status = 'not_required' WHERE id = 10")
        conn.execute('DELETE FROM assignments WHERE id IN (?, ?)', (assignment_id, 9222))
        conn.execute("DELETE FROM assignments WHERE date IN ('2026-09-11', '2026-09-16')")
        conn.commit()
        conn.close()

    def test_psi_requirement_can_change_with_only_new_assignments(self):
        conn = sqlite3.connect(self.path)
        conn.execute("INSERT INTO assignments (id, task_id, date, status) VALUES (220, 10, '2026-09-20', 'new')")
        conn.commit()
        conn.close()
        payload = {
            'task_id': 10, 'team_id': 1, 'name': 'Original task',
            'description': 'Original description', 'criticality': 'medium',
            'segment_id': 1, 'psi_status': 'required',
        }
        with self.login() as client:
            response = client.post('/api/task', json=payload)
            self.assertEqual(200, response.status_code)
            task = client.get('/api/task/10').json()
            self.assertTrue(task['has_assignments'])
            self.assertFalse(task['has_active_assignments'])

        conn = sqlite3.connect(self.path)
        conn.execute("UPDATE tasks SET psi_status = 'passed' WHERE id = 10")
        conn.commit()
        conn.close()
        payload['psi_status'] = 'not_required'
        with self.login() as client:
            response = client.post('/api/task', json=payload)
            self.assertEqual(200, response.status_code)

        conn = sqlite3.connect(self.path)
        conn.execute("UPDATE assignments SET status = 'planned' WHERE id = 220")
        conn.commit()
        conn.close()
        payload['psi_status'] = 'required'
        with self.login() as client:
            response = client.post('/api/task', json=payload)
            self.assertEqual(400, response.status_code)
            self.assertIn('активные назначения', response.json()['error'])

        conn = sqlite3.connect(self.path)
        conn.execute('DELETE FROM assignments WHERE id = 220')
        conn.execute("UPDATE tasks SET psi_status = 'not_required' WHERE id = 10")
        conn.execute("DELETE FROM task_history WHERE task_id = 10 AND field_name = 'psi_status'")
        conn.commit()
        conn.close()


if __name__ == '__main__':
    unittest.main()
