import json
import os
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import db
from backend.application import app
import backend.db.sqlite as sqlite_backend


class TaskRolloutTemplateTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, 'test.db')
        self.old_path = sqlite_backend.DB_PATH
        sqlite_backend.DB_PATH = self.path
        db.init_db()
        self.sql("INSERT INTO segments (id, name) VALUES (1, 'One'), (2, 'Two')")
        self.sql("INSERT INTO teams (id, name) VALUES (1, 'Team'), (2, 'Other')")
        self.sql("INSERT INTO blocks (id, name) VALUES (1, 'A'), (2, 'B')")
        self.sql("INSERT INTO block_templates (id, name, segment_id) VALUES "
                 "(1, 'First', 1), (2, 'Second', 1), (3, 'Other segment', 2), (4, 'Forbidden', 1)")
        self.sql('INSERT INTO template_blocks (template_id, block_id, schedule_offset) '
                 'VALUES (1, 1, 0), (2, 2, 0), (3, 1, 0)')
        self.sql('INSERT INTO team_templates (team_id, template_id) VALUES (1, 1), (1, 2), (1, 3)')
        self.sql("INSERT INTO tasks (id, name, team_id, segment_id, completion_template_id) "
                 "VALUES (10, 'Existing', 1, 1, 1), (11, 'Legacy', 1, 1, NULL)")
        self.client = TestClient(app, raise_server_exceptions=False)
        self.assertEqual(200, self.client.post('/login', data={
            'login': 'admin', 'password': 'q12345678',
        }).status_code)

    def tearDown(self):
        self.client.close()
        sqlite_backend.DB_PATH = self.old_path
        self.temp.cleanup()

    def sql(self, statement, params=()):
        conn = sqlite3.connect(self.path)
        try:
            result = conn.execute(statement, params).fetchall()
            conn.commit()
            return result
        finally:
            conn.close()

    def save(self, task_id=10, **changes):
        payload = dict(task_id=task_id, team_id=1, name='Changed', segment_id=1)
        payload.update(changes)
        return self.client.post('/api/task', json=payload)

    def assign(self, task_id=10, status='new', date='2026-11-04'):
        response = self.client.post('/api/assignment', json={
            'task_id': task_id, 'date': date, 'block': 'A', 'status': status,
        })
        self.assertEqual(200, response.status_code, response.text)

    def test_create_requires_matching_allowed_template_and_explicit_segment(self):
        for changes in ({}, {'completion_template_id': 999}, {'completion_template_id': 3},
                        {'completion_template_id': 4}, {'completion_template_id': 1, 'segment_id': None}):
            with self.subTest(changes=changes):
                self.assertEqual(400, self.save(None, **changes).status_code)
        self.assertEqual([(2,)], self.sql('SELECT COUNT(*) FROM tasks'))
        response = self.save(None, completion_template_id=1)
        self.assertEqual(200, response.status_code, response.text)
        task_id = response.json()['id']
        data = self.client.get('/api/task/{}'.format(task_id)).json()
        self.assertEqual((1, 'First'), (data['completion_template_id'], data['completion_template_name']))
        snapshot = self.sql("SELECT new_value FROM task_history WHERE task_id = ? AND action = 'create'",
                            (task_id,))[0][0]
        self.assertEqual(1, json.loads(snapshot)['completion_template_id'])

    def test_read_contract_including_archive_and_legacy_null(self):
        items = self.client.get('/api/tasks/1').json()['tasks']
        self.assertEqual({10: 1, 11: None}, {t['id']: t['completion_template_id'] for t in items})
        self.sql("UPDATE tasks SET task_status = 'done', completed_at = CURRENT_TIMESTAMP WHERE id = 10")
        archive = self.client.get('/api/tasks/1/archive').json()['tasks']
        self.assertEqual('First', archive[0]['completion_template_name'])
        self.assertIsNone(self.client.get('/api/task/11').json()['completion_template_name'])

    def test_every_non_deleted_assignment_blocks_changes_and_rolls_back_other_fields(self):
        for status in ('new', 'planned', 'rollback', 'success', 'unsuccessful', 'cancelled'):
            with self.subTest(status=status):
                self.sql('DELETE FROM assignments')
                self.assign(status=status)
                self.assertEqual(400, self.save(completion_template_id=2, dependency_ids=[11]).status_code)
                self.assertEqual(400, self.save(segment_id=2, completion_template_id=3).status_code)
                self.assertEqual([('Existing', 1, 1)], self.sql(
                    'SELECT name, segment_id, completion_template_id FROM tasks WHERE id = 10'))
                self.assertEqual([], self.sql('SELECT * FROM task_dependencies'))
                self.assertEqual([], self.sql('SELECT * FROM task_history'))
                self.assertEqual(200, self.save(name='Existing', completion_template_id=1).status_code)

    def test_unlock_only_after_all_assignments_deleted_and_record_history(self):
        self.assign()
        self.assign(date='2026-11-05')
        assignment_ids = [row[0] for row in self.sql('SELECT id FROM assignments ORDER BY id')]
        self.client.delete('/api/assignment/{}'.format(assignment_ids[0]))
        self.assertEqual(400, self.save(completion_template_id=2).status_code)
        self.client.delete('/api/assignment/{}'.format(assignment_ids[1]))
        self.assertEqual(200, self.save(segment_id=2, completion_template_id=3).status_code)
        self.assertEqual([(1, 3)], self.sql(
            "SELECT CAST(old_value AS INTEGER), CAST(new_value AS INTEGER) FROM task_history "
            "WHERE task_id = 10 AND field_name = 'completion_template_id'"))

    def test_legacy_fill_once_with_assignments_and_unchanged_segment(self):
        self.assign(task_id=11)
        self.assertEqual(200, self.save(11, description='Legacy edit').status_code)
        self.assertEqual(400, self.save(11, segment_id=2, completion_template_id=3).status_code)
        self.assertEqual(200, self.save(11, completion_template_id=2).status_code)
        self.assertEqual(400, self.save(11, completion_template_id=1).status_code)

    def test_omitted_template_preserves_selection_but_explicit_null_is_rejected(self):
        self.assertEqual(200, self.save(description='Allowed').status_code)
        self.assertEqual(400, self.save(completion_template_id=None).status_code)
        self.assertEqual([(1,)], self.sql('SELECT completion_template_id FROM tasks WHERE id = 10'))

    def test_terminal_task_does_not_get_legacy_exception(self):
        self.sql("UPDATE tasks SET task_status = 'done' WHERE id = 11")
        self.assertEqual(400, self.save(11, completion_template_id=1).status_code)

    def test_revoked_and_historically_mismatched_template_survive_unrelated_edits(self):
        self.sql('DELETE FROM team_templates WHERE template_id = 1')
        self.assertEqual(200, self.save(description='Still editable', completion_template_id=1).status_code)
        self.sql('UPDATE tasks SET segment_id = 2 WHERE id = 10')
        self.assertEqual(200, self.save(segment_id=2, description='Historical', completion_template_id=1).status_code)
        self.assertEqual('First', self.client.get('/api/task/10').json()['completion_template_name'])

    def test_bulk_cannot_choose_template_and_keeps_multiple_task_manual_requests(self):
        assignment = dict(task_id=10, date='2026-11-04', block='A', status='new')
        for template_id, task_id in ((2, 10), (1, 11)):
            response = self.client.post('/api/assignments/bulk', json={
                'template_id': template_id, 'assignments': [dict(assignment, task_id=task_id)],
            })
            self.assertEqual(400, response.status_code)
            self.assertEqual([], self.sql('SELECT id FROM assignments'))
        response = self.client.post('/api/assignments/bulk', json={'template_id': 1, 'assignments': [assignment]})
        self.assertEqual(200, response.status_code, response.text)
        response = self.client.post('/api/assignments/bulk', json={'assignments': [
            dict(assignment, date='2026-11-05'), dict(assignment, task_id=11),
        ]})
        self.assertEqual(200, response.status_code)
        self.assertEqual([(10, 1), (11, None)], self.sql('SELECT id, completion_template_id FROM tasks ORDER BY id'))

    def test_referenced_template_is_protected_including_terminal_and_deleted_tasks(self):
        for task_status, is_deleted in (('new', 0), ('done', 0), ('cancelled', 1)):
            self.sql('UPDATE tasks SET task_status = ?, is_deleted = ? WHERE id = 10', (task_status, is_deleted))
            self.assertEqual(400, self.client.delete('/api/block-templates/1').status_code)
            response = self.client.put('/api/block-templates/1', json={
                'name': 'Must rollback', 'segment_id': 2, 'entries': [],
            })
            self.assertEqual(400, response.status_code)
            self.assertEqual([('First', 1)], self.sql('SELECT name, segment_id FROM block_templates WHERE id = 1'))
            self.assertEqual([(1,)], self.sql('SELECT block_id FROM template_blocks WHERE template_id = 1'))
        self.assertEqual(200, self.client.put('/api/block-templates/1', json={
            'name': 'Updated', 'segment_id': 1, 'entries': [{'block_id': 2, 'shift_days': 3}],
        }).status_code)
        self.assertEqual([(2, 3)], self.sql('SELECT block_id, schedule_offset FROM template_blocks WHERE template_id = 1'))
        self.assertEqual(200, self.client.put('/api/block-templates/2', json={
            'name': 'Unused', 'segment_id': 2, 'entries': [],
        }).status_code)
        self.assertEqual(200, self.client.delete('/api/block-templates/2').status_code)

    def test_assignment_commit_before_configuration_read_is_observed(self):
        held = threading.Event()
        release = threading.Event()

        def create_assignment_with_lock():
            conn = db.get_db_connection()
            try:
                conn.execute('BEGIN IMMEDIATE')
                conn.execute("INSERT INTO assignments (task_id, date, block, status) VALUES (10, '2026-11-04', 'A', 'new')")
                held.set()
                if not release.wait(3):
                    raise RuntimeError('Test did not release writer')
                conn.commit()
            finally:
                conn.close()

        def change_configuration():
            return db.create_or_update_task(10, 1, 'Concurrent', None, segment_id=1, completion_template_id=2)

        with ThreadPoolExecutor(max_workers=2) as pool:
            writer = pool.submit(create_assignment_with_lock)
            self.assertTrue(held.wait(3))
            editor = pool.submit(change_configuration)
            release.set()
            writer.result(timeout=4)
            with self.assertRaises(db.IntegrityConstraintError):
                editor.result(timeout=4)
        self.assertEqual([(1,)], self.sql('SELECT completion_template_id FROM tasks WHERE id = 10'))

    def test_dependency_failure_rolls_back_selection_and_history(self):
        with patch.object(db, 'set_task_dependencies', side_effect=RuntimeError('failure')):
            response = self.save(completion_template_id=2, dependency_ids=[11])
        self.assertEqual(500, response.status_code)
        self.assertEqual([(1, 'Existing')], self.sql('SELECT completion_template_id, name FROM tasks WHERE id = 10'))
        self.assertEqual([], self.sql('SELECT id FROM task_history'))
