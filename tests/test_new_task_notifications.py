import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

import auth
import db
import db.sqlite as sqlite_backend
from db.sqlite_migration_steps import SQLiteMigrationSteps
from support_planner import app


class NewTaskNotificationMigrationTest(unittest.TestCase):
    def test_migration_is_idempotent_and_backfills_current_cursor(self):
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        conn.executescript('''
            CREATE TABLE users (id INTEGER PRIMARY KEY);
            CREATE TABLE tasks (id INTEGER PRIMARY KEY);
            CREATE TABLE task_history (
                id INTEGER PRIMARY KEY, task_id INTEGER, action TEXT, changed_at TEXT
            );
            INSERT INTO users VALUES (1);
            INSERT INTO tasks VALUES (10);
            INSERT INTO task_history VALUES (5, 10, 'create', '2026-08-01 10:00:00');
        ''')
        SQLiteMigrationSteps.migrate_add_new_task_notifications(conn)
        SQLiteMigrationSteps.migrate_add_seen_new_task_events(conn)
        SQLiteMigrationSteps.migrate_add_new_task_notifications(conn)
        SQLiteMigrationSteps.migrate_add_seen_new_task_events(conn)
        self.assertEqual(('2026-08-01 10:00:00', 5), tuple(conn.execute(
            'SELECT new_tasks_seen_at, new_tasks_seen_history_id FROM user_new_task_notification_state WHERE user_id=1'
        ).fetchone()))
        self.assertEqual(1, conn.execute('SELECT COUNT(*) FROM user_new_task_notification_state').fetchone()[0])
        self.assertIsNotNone(conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='user_new_task_notification_seen_events'"
        ).fetchone())


class NewTaskNotificationsApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        handle, cls.path = tempfile.mkstemp(suffix='.db')
        os.close(handle)
        cls.old_path = sqlite_backend.DB_PATH
        sqlite_backend.DB_PATH = cls.path
        db.init_db()
        conn = sqlite3.connect(cls.path)
        conn.executescript('''
            INSERT INTO teams (id, name) VALUES (1, 'Allowed'), (2, 'Denied');
            INSERT INTO segments (id, name) VALUES (1, 'Segment');
        ''')
        password = auth.hash_password('password123')
        conn.execute('''INSERT INTO users (id, first_name, role, login, password_hash, is_assignee)
                        VALUES (2, 'Reader', 'user', 'reader-notifications', ?, 1),
                               (3, 'Author', 'editor', 'author-notifications', ?, 1)''', (password, password))
        conn.execute('INSERT INTO user_team_access VALUES (2, 1)')
        conn.execute("INSERT INTO user_new_task_notification_state VALUES (2, '', 0)")
        cls.now = datetime.now(timezone.utc).replace(microsecond=0)
        for task_id, team_id, name, author, deleted, status in (
            (10, 1, 'Visible', 3, 0, 'new'),
            (11, 2, 'Denied', 3, 0, 'new'),
            (12, 1, 'Own', 2, 0, 'new'),
            (13, 1, 'Deleted', 3, 1, 'new'),
            (14, 1, 'Completed', 3, 0, 'done'),
            (17, 1, 'Cancelled', 3, 0, 'cancelled'),
        ):
            conn.execute('''INSERT INTO tasks
                (id, team_id, segment_id, name, task_status, is_deleted) VALUES (?, ?, 1, ?, ?, ?)''',
                (task_id, team_id, name, status, deleted))
            conn.execute('''INSERT INTO task_history
                (task_id, action, changed_at, changed_by_user_id) VALUES (?, 'create', ?, ?)''',
                (task_id, (cls.now + timedelta(seconds=task_id)).strftime('%Y-%m-%d %H:%M:%S'), author))
        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        sqlite_backend.DB_PATH = cls.old_path
        for suffix in ('', '-wal', '-shm'):
            try: os.remove(cls.path + suffix)
            except FileNotFoundError: pass

    def login(self):
        client = TestClient(app)
        self.assertEqual(200, client.post('/login', data={
            'login': 'reader-notifications', 'password': 'password123'}).status_code)
        return client

    def setUp(self):
        conn = sqlite3.connect(self.path)
        conn.execute('DELETE FROM task_history WHERE task_id = 16')
        conn.execute('DELETE FROM tasks WHERE id = 16')
        conn.execute('DELETE FROM user_new_task_notification_seen_events')
        conn.execute("UPDATE tasks SET task_status = 'done' WHERE id = 14")
        conn.execute("UPDATE tasks SET task_status = 'cancelled' WHERE id = 17")
        conn.execute("UPDATE user_new_task_notification_state SET new_tasks_seen_at = '', new_tasks_seen_history_id = 0 WHERE user_id = 2")
        conn.commit()
        conn.close()

    def test_preview_filters_access_author_deleted_and_terminal_tasks(self):
        with self.login() as client:
            response = client.get('/api/notifications/new-tasks/preview')
            self.assertEqual(200, response.status_code)
            data = response.json()
            self.assertEqual({10}, {item['task_id'] for item in data['items']})
            self.assertEqual(1, data['total'])

    def test_unseen_restored_task_returns_while_creation_is_fresh(self):
        conn = sqlite3.connect(self.path)
        conn.execute("UPDATE tasks SET task_status = 'new' WHERE id = 14")
        conn.commit(); conn.close()
        with self.login() as client:
            preview = client.get('/api/notifications/new-tasks/preview').json()
            page = client.get('/api/notifications/new-tasks').json()
            self.assertEqual({10, 14}, {item['task_id'] for item in preview['items']})
            self.assertEqual({10, 14}, {item['task_id'] for item in page['items']})
            self.assertEqual(2, preview['total'])

    def test_watermark_prevents_race_and_confirmation_is_monotonic(self):
        with self.login() as client:
            first = client.get('/api/notifications/new-tasks/preview').json()
            old_watermark = first['watermark']
            conn = sqlite3.connect(self.path)
            conn.execute("INSERT INTO tasks (id, team_id, segment_id, name) VALUES (15, 1, 1, 'Later')")
            conn.execute("INSERT INTO task_history (task_id, action, changed_at, changed_by_user_id) VALUES (15, 'create', ?, 3)",
                         ((self.now + timedelta(seconds=100)).strftime('%Y-%m-%d %H:%M:%S'),))
            conn.commit(); conn.close()
            self.assertEqual(first['total'], client.get('/api/notifications/new-tasks', params={
                'watermark_at': old_watermark['changed_at'], 'watermark_id': old_watermark['history_id']}).json()['total'])
            self.assertEqual(200, client.post('/api/notifications/new-tasks/seen', json={'watermark': old_watermark}).status_code)
            after = client.get('/api/notifications/new-tasks/preview').json()
            self.assertEqual([15], [item['task_id'] for item in after['items']])
            client.post('/api/notifications/new-tasks/seen', json={'watermark': old_watermark})
            self.assertEqual([15], [item['task_id'] for item in client.get('/api/notifications/new-tasks/preview').json()['items']])

    def test_item_confirmation_is_idempotent_and_keeps_other_items(self):
        with self.login() as client:
            response = client.post('/api/notifications/new-tasks/seen-items', json={'task_ids': [10, 10, 14]})
            self.assertEqual(200, response.status_code)
            self.assertEqual(2, response.json()['marked'])
            self.assertEqual([], [item['task_id'] for item in client.get('/api/notifications/new-tasks/preview').json()['items']])
            again = client.post('/api/notifications/new-tasks/seen-items', json={'task_ids': [10, 14]})
            self.assertEqual({'success': True, 'marked': 0}, again.json())

    def test_item_confirmation_ignores_own_denied_deleted_and_expired_items(self):
        conn = sqlite3.connect(self.path)
        conn.execute("INSERT INTO tasks (id, team_id, segment_id, name) VALUES (16, 1, 1, 'Expired')")
        conn.execute("INSERT INTO task_history (task_id, action, changed_at, changed_by_user_id) VALUES (16, 'create', '2020-01-01 00:00:00', 3)")
        conn.commit(); conn.close()
        with self.login() as client:
            response = client.post('/api/notifications/new-tasks/seen-items', json={'task_ids': [11, 12, 13, 16, 999]})
            self.assertEqual({'success': True, 'marked': 0}, response.json())
            self.assertEqual({10}, {item['task_id'] for item in client.get('/api/notifications/new-tasks/preview').json()['items']})

    def test_item_confirmation_rejects_oversized_payload_and_requires_authentication(self):
        with self.login() as client:
            self.assertEqual(400, client.post('/api/notifications/new-tasks/seen-items',
                                              json={'task_ids': list(range(101))}).status_code)
        self.assertEqual(401, TestClient(app).post('/api/notifications/new-tasks/seen-items',
                                                   json={'task_ids': [10]}).status_code)

    def test_preview_excludes_expired_items(self):
        conn = sqlite3.connect(self.path)
        conn.execute("INSERT INTO tasks (id, team_id, segment_id, name) VALUES (16, 1, 1, 'Expired')")
        conn.execute("INSERT INTO task_history (task_id, action, changed_at, changed_by_user_id) VALUES (16, 'create', '2020-01-01 00:00:00', 3)")
        conn.commit(); conn.close()
        with self.login() as client:
            self.assertNotIn(16, {item['task_id'] for item in client.get('/api/notifications/new-tasks/preview').json()['items']})

    def test_cleanup_removes_only_expired_seen_events(self):
        conn = sqlite3.connect(self.path)
        conn.execute("INSERT INTO tasks (id, team_id, segment_id, name) VALUES (16, 1, 1, 'Expired')")
        conn.execute("INSERT INTO task_history (id, task_id, action, changed_at, changed_by_user_id) VALUES (160, 16, 'create', '2020-01-01 00:00:00', 3)")
        conn.execute("INSERT INTO user_new_task_notification_seen_events VALUES (2, 160, '2020-01-02 00:00:00')")
        conn.execute("INSERT INTO user_new_task_notification_seen_events VALUES (2, 1, '2099-01-01 00:00:00')")
        conn.commit(); conn.close()
        self.assertEqual(1, db.cleanup_seen_new_task_events())
        conn = sqlite3.connect(self.path)
        self.assertEqual([(2, 1)], conn.execute(
            'SELECT user_id, task_history_id FROM user_new_task_notification_seen_events'
        ).fetchall())
        conn.close()


if __name__ == '__main__':
    unittest.main()
