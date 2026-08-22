import os
import sqlite3
import tempfile
import unittest

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
        SQLiteMigrationSteps.migrate_add_new_task_notifications(conn)
        self.assertEqual(('2026-08-01 10:00:00', 5), tuple(conn.execute(
            'SELECT new_tasks_seen_at, new_tasks_seen_history_id FROM user_notification_state WHERE user_id=1'
        ).fetchone()))
        self.assertEqual(1, conn.execute('SELECT COUNT(*) FROM user_notification_state').fetchone()[0])


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
        conn.execute("INSERT INTO user_notification_state VALUES (2, '', 0)")
        for task_id, team_id, name, author, deleted, status in (
            (10, 1, 'Visible', 3, 0, 'new'),
            (11, 2, 'Denied', 3, 0, 'new'),
            (12, 1, 'Own', 2, 0, 'new'),
            (13, 1, 'Deleted', 3, 1, 'new'),
            (14, 1, 'Completed', 3, 0, 'done'),
        ):
            conn.execute('''INSERT INTO tasks
                (id, team_id, segment_id, name, task_status, is_deleted) VALUES (?, ?, 1, ?, ?, ?)''',
                (task_id, team_id, name, status, deleted))
            conn.execute('''INSERT INTO task_history
                (task_id, action, changed_at, changed_by_user_id) VALUES (?, 'create', ?, ?)''',
                (task_id, f'2026-08-01 10:00:{task_id}', author))
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

    def test_preview_filters_access_author_and_deleted_but_keeps_terminal(self):
        with self.login() as client:
            response = client.get('/api/notifications/new-tasks/preview')
            self.assertEqual(200, response.status_code)
            data = response.json()
            self.assertEqual({10, 14}, {item['task_id'] for item in data['items']})
            self.assertEqual(2, data['total'])

    def test_watermark_prevents_race_and_confirmation_is_monotonic(self):
        with self.login() as client:
            first = client.get('/api/notifications/new-tasks/preview').json()
            old_watermark = first['watermark']
            conn = sqlite3.connect(self.path)
            conn.execute("INSERT INTO tasks (id, team_id, segment_id, name) VALUES (15, 1, 1, 'Later')")
            conn.execute("INSERT INTO task_history (task_id, action, changed_at, changed_by_user_id) VALUES (15, 'create', '2026-08-02 10:00:00', 3)")
            conn.commit(); conn.close()
            self.assertEqual(first['total'], client.get('/api/notifications/new-tasks', params={
                'watermark_at': old_watermark['changed_at'], 'watermark_id': old_watermark['history_id']}).json()['total'])
            self.assertEqual(200, client.post('/api/notifications/new-tasks/seen', json={'watermark': old_watermark}).status_code)
            after = client.get('/api/notifications/new-tasks/preview').json()
            self.assertEqual([15], [item['task_id'] for item in after['items']])
            client.post('/api/notifications/new-tasks/seen', json={'watermark': old_watermark})
            self.assertEqual([15], [item['task_id'] for item in client.get('/api/notifications/new-tasks/preview').json()['items']])


if __name__ == '__main__':
    unittest.main()
