import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import db.sqlite as sqlite_backend
from db.sqlite import SQLiteBackend
from db.sqlite_functions import register_sqlite_functions
from db.sqlite_migrations import Migration, current_version, run_migrations


class SQLiteInfrastructureTests(unittest.TestCase):
    def test_registered_functions_are_available(self):
        conn = sqlite3.connect(':memory:')
        try:
            register_sqlite_functions(conn)
            self.assertEqual(conn.execute("SELECT fuzzy_word_in('планирование', 'планироване')").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT casefold('ТЕСТ')").fetchone()[0], 'тест')
        finally:
            conn.close()

    def test_migration_registry_applies_each_version_once(self):
        conn = sqlite3.connect(':memory:')
        calls = []
        migrations = (
            Migration(1, 'first', lambda connection: calls.append('first')),
            Migration(2, 'second', lambda connection: calls.append('second')),
        )
        try:
            run_migrations(conn, migrations)
            run_migrations(conn, migrations)
            self.assertEqual(calls, ['first', 'second'])
            self.assertEqual(current_version(conn), 2)
        finally:
            conn.close()

    def test_migration_registry_rejects_version_gaps(self):
        conn = sqlite3.connect(':memory:')
        try:
            with self.assertRaisesRegex(RuntimeError, 'expected version 1, got 2'):
                run_migrations(conn, (Migration(2, 'gap', lambda connection: None),))
        finally:
            conn.close()

    def test_fresh_install_reaches_current_schema_version(self):
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        try:
            SQLiteBackend().init_schema(conn)
            self.assertEqual(current_version(conn), 13)
            tables = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )}
            self.assertTrue({'users', 'tasks', 'assignments', 'task_history'} <= tables)
            self.assertEqual(conn.execute("SELECT role FROM users WHERE login = 'admin'").fetchone()[0], 'admin')
        finally:
            conn.close()

    def test_legacy_upgrade_preserves_rows(self):
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        conn.executescript('''
            CREATE TABLE teams (id INTEGER PRIMARY KEY, name TEXT UNIQUE);
            CREATE TABLE employees (
                id INTEGER PRIMARY KEY, last_name TEXT NOT NULL, first_name TEXT NOT NULL,
                middle_name TEXT, password_hash TEXT, role TEXT NOT NULL DEFAULT 'user'
            );
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY, team_id INTEGER NOT NULL, name TEXT NOT NULL,
                description TEXT, criticality TEXT NOT NULL DEFAULT 'medium',
                task_status TEXT NOT NULL DEFAULT 'new', is_deleted INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE assignments (
                id INTEGER PRIMARY KEY, task_id INTEGER NOT NULL, date DATE NOT NULL,
                block TEXT, status TEXT NOT NULL DEFAULT 'new', employee_id INTEGER,
                comment TEXT, is_psi INTEGER NOT NULL DEFAULT 0, time_spent TEXT,
                is_deleted INTEGER NOT NULL DEFAULT 0
            );
            INSERT INTO teams (id, name) VALUES (1, 'Legacy team');
            INSERT INTO employees (id, last_name, first_name, role) VALUES (2, 'Иванов', 'Иван', 'user');
            INSERT INTO tasks (id, team_id, name, criticality) VALUES (3, 1, 'Legacy task', 'high');
            INSERT INTO assignments (id, task_id, date, employee_id) VALUES (4, 3, '2026-01-01', 2);
        ''')
        try:
            SQLiteBackend().init_schema(conn)
            self.assertEqual(current_version(conn), 13)
            self.assertEqual(conn.execute('SELECT name FROM tasks WHERE id = 3').fetchone()[0], 'Legacy task')
            self.assertEqual(conn.execute('SELECT user_id FROM assignments WHERE id = 4').fetchone()[0], 2)
            task_columns = {row[1] for row in conn.execute('PRAGMA table_info(tasks)')}
            self.assertTrue({
                'priority', 'criticality', 'segment_id', 'completed_at', 'completion_template_id', 'psi_status',
                'instruction_url',
            } <= task_columns)
        finally:
            conn.close()

    def test_instruction_url_migration_preserves_description_and_is_idempotent(self):
        conn = sqlite3.connect(':memory:')
        conn.executescript('''
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY,
                description TEXT
            );
            INSERT INTO tasks (id, description)
            VALUES (1, 'Инструкция: https://example.test/docs');
        ''')
        try:
            steps = sqlite_backend.SQLiteMigrationSteps()
            steps.migrate_add_task_instruction_url(conn)
            steps.migrate_add_task_instruction_url(conn)

            columns = [row[1] for row in conn.execute('PRAGMA table_info(tasks)')]
            self.assertEqual(1, columns.count('instruction_url'))
            self.assertEqual(
                ('Инструкция: https://example.test/docs', None),
                conn.execute('SELECT description, instruction_url FROM tasks WHERE id = 1').fetchone(),
            )
        finally:
            conn.close()

    def test_backend_connections_enable_wal_and_foreign_keys(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            old_path = sqlite_backend.DB_PATH
            sqlite_backend.DB_PATH = str(Path(temp_dir) / 'lifecycle.db')
            try:
                backend = SQLiteBackend()
                conn = backend.connect()
                backend.setup_connection(conn)
                self.assertEqual(conn.execute('PRAGMA journal_mode').fetchone()[0], 'wal')
                self.assertEqual(conn.execute('PRAGMA foreign_keys').fetchone()[0], 1)
                conn.close()
            finally:
                sqlite_backend.DB_PATH = old_path

    def _current_database_at_version_12(self):
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        SQLiteBackend().init_schema(conn)
        conn.execute('DELETE FROM schema_migrations WHERE version = 13')
        conn.execute('PRAGMA user_version = 12')
        conn.commit()
        return conn

    def test_version_12_legacy_notification_table_is_repaired(self):
        conn = self._current_database_at_version_12()
        try:
            conn.execute('''INSERT INTO users
                (id, first_name, role, login, is_assignee) VALUES (101, 'Legacy', 'user', 'legacy', 1)''')
            conn.execute('ALTER TABLE user_new_task_notification_state RENAME TO user_notification_state')
            conn.execute('''INSERT INTO user_notification_state
                (user_id, new_tasks_seen_at, new_tasks_seen_history_id)
                VALUES (101, '2026-09-01 10:00:00', 41)''')
            conn.execute('DROP TABLE schema_migrations')
            conn.commit()

            SQLiteBackend().init_schema(conn)

            self.assertEqual(current_version(conn), 13)
            self.assertIsNone(conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='user_notification_state'"
            ).fetchone())
            self.assertEqual(
                ('2026-09-01 10:00:00', 41),
                tuple(conn.execute('''SELECT new_tasks_seen_at, new_tasks_seen_history_id
                    FROM user_new_task_notification_state WHERE user_id = 101''').fetchone()),
            )
            self.assertEqual(13, conn.execute('SELECT COUNT(*) FROM schema_migrations').fetchone()[0])
        finally:
            conn.close()

    def test_version_11_legacy_notification_table_runs_steps_12_and_13(self):
        conn = self._current_database_at_version_12()
        try:
            conn.execute('''INSERT INTO users
                (id, first_name, role, login, is_assignee) VALUES (111, 'Version11', 'user', 'v11', 1)''')
            conn.execute('''INSERT INTO user_new_task_notification_state
                (user_id, new_tasks_seen_at, new_tasks_seen_history_id)
                VALUES (111, '2026-08-31 09:00:00', 31)''')
            conn.execute('DROP TABLE user_new_task_notification_seen_events')
            conn.execute('ALTER TABLE user_new_task_notification_state RENAME TO user_notification_state')
            conn.execute('DROP TABLE schema_migrations')
            conn.execute('PRAGMA user_version = 11')
            conn.commit()

            SQLiteBackend().init_schema(conn)

            self.assertEqual(current_version(conn), 13)
            self.assertIsNotNone(conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='user_new_task_notification_seen_events'"
            ).fetchone())
            self.assertEqual(
                ('2026-08-31 09:00:00', 31),
                tuple(conn.execute('''SELECT new_tasks_seen_at, new_tasks_seen_history_id
                    FROM user_new_task_notification_state WHERE user_id = 111''').fetchone()),
            )
            self.assertIsNone(conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='user_notification_state'"
            ).fetchone())
            self.assertEqual(13, conn.execute('SELECT COUNT(*) FROM schema_migrations').fetchone()[0])
        finally:
            conn.close()

    def test_version_12_both_notification_tables_merge_maximum_cursor(self):
        conn = self._current_database_at_version_12()
        try:
            conn.execute('''INSERT INTO users
                (id, first_name, role, login, is_assignee) VALUES (102, 'Both', 'user', 'both', 1)''')
            conn.execute('''INSERT INTO user_new_task_notification_state VALUES
                (102, '2026-09-02 10:00:00', 10)''')
            conn.execute('''CREATE TABLE user_notification_state (
                user_id INTEGER PRIMARY KEY,
                new_tasks_seen_at TEXT NOT NULL,
                new_tasks_seen_history_id INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )''')
            conn.execute('''INSERT INTO user_notification_state VALUES
                (102, '2026-09-02 10:00:00', 12)''')
            conn.commit()

            SQLiteBackend().init_schema(conn)

            self.assertEqual(
                ('2026-09-02 10:00:00', 12),
                tuple(conn.execute('''SELECT new_tasks_seen_at, new_tasks_seen_history_id
                    FROM user_new_task_notification_state WHERE user_id = 102''').fetchone()),
            )
            self.assertIsNone(conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='user_notification_state'"
            ).fetchone())
        finally:
            conn.close()

    def test_version_12_without_notification_state_recreates_and_backfills(self):
        conn = self._current_database_at_version_12()
        try:
            conn.execute('DROP TABLE user_new_task_notification_state')
            conn.execute('''INSERT INTO users
                (id, first_name, role, login, is_assignee) VALUES (103, 'Missing', 'user', 'missing', 1)''')
            conn.commit()

            SQLiteBackend().init_schema(conn)

            self.assertIsNotNone(conn.execute(
                'SELECT 1 FROM user_new_task_notification_state WHERE user_id = 103'
            ).fetchone())
            self.assertEqual(current_version(conn), 13)
        finally:
            conn.close()

    def test_version_12_canonical_notification_state_is_preserved(self):
        conn = self._current_database_at_version_12()
        try:
            conn.execute('''INSERT INTO users
                (id, first_name, role, login, is_assignee) VALUES (104, 'Current', 'user', 'current', 1)''')
            conn.execute("INSERT INTO user_new_task_notification_state VALUES (104, '2026-09-03', 17)")
            conn.commit()

            SQLiteBackend().init_schema(conn)

            self.assertEqual(
                ('2026-09-03', 17),
                tuple(conn.execute('''SELECT new_tasks_seen_at, new_tasks_seen_history_id
                    FROM user_new_task_notification_state WHERE user_id = 104''').fetchone()),
            )
        finally:
            conn.close()

    def test_incompatible_legacy_table_rolls_back_version_13(self):
        conn = self._current_database_at_version_12()
        try:
            conn.execute('DROP TABLE user_new_task_notification_state')
            conn.execute('CREATE TABLE user_notification_state (user_id INTEGER PRIMARY KEY)')
            conn.commit()

            with self.assertRaisesRegex(RuntimeError, 'incompatible columns'):
                SQLiteBackend().init_schema(conn)

            self.assertEqual(current_version(conn), 12)
            self.assertIsNotNone(conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='user_notification_state'"
            ).fetchone())
            self.assertEqual(12, conn.execute('SELECT COUNT(*) FROM schema_migrations').fetchone()[0])
        finally:
            conn.close()

    def test_orphan_legacy_row_rolls_back_version_13(self):
        conn = self._current_database_at_version_12()
        try:
            conn.execute('DROP TABLE user_new_task_notification_state')
            conn.execute('''CREATE TABLE user_notification_state (
                user_id INTEGER PRIMARY KEY,
                new_tasks_seen_at TEXT NOT NULL,
                new_tasks_seen_history_id INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )''')
            conn.execute("INSERT INTO user_notification_state VALUES (999999, '', 0)")
            conn.commit()

            with self.assertRaisesRegex(RuntimeError, 'missing user 999999'):
                SQLiteBackend().init_schema(conn)

            self.assertEqual(current_version(conn), 12)
        finally:
            conn.close()

    def test_failed_postcondition_rolls_back_operation_and_version(self):
        conn = sqlite3.connect(':memory:')
        try:
            def operation(connection):
                connection.execute('CREATE TABLE partial_change (id INTEGER)')

            def reject(_connection):
                raise RuntimeError('postcondition rejected')

            with self.assertRaisesRegex(RuntimeError, 'postcondition rejected'):
                run_migrations(conn, (Migration(1, 'atomic', operation, postcondition=reject),))

            self.assertEqual(current_version(conn), 0)
            self.assertIsNone(conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='partial_change'"
            ).fetchone())
        finally:
            conn.close()

    def test_future_database_version_is_rejected(self):
        conn = sqlite3.connect(':memory:')
        try:
            conn.execute('PRAGMA user_version = 2')
            with self.assertRaisesRegex(RuntimeError, 'newer than supported'):
                run_migrations(conn, (Migration(1, 'first', lambda connection: None),))
        finally:
            conn.close()

    def test_migration_checksum_mismatch_is_rejected(self):
        conn = sqlite3.connect(':memory:')
        try:
            run_migrations(conn, (Migration(1, 'first', lambda connection: None, checksum='original'),))
            with self.assertRaisesRegex(RuntimeError, 'journal mismatch at version 1'):
                run_migrations(conn, (Migration(1, 'first', lambda connection: None, checksum='changed'),))
        finally:
            conn.close()

    def test_predeploy_cli_success_and_future_version_failure(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / 'predeploy.db'
            success = subprocess.run(
                [sys.executable, 'migrate_database.py', '--database', str(database)],
                cwd=root, capture_output=True, text=True, encoding='utf-8', check=False,
            )
            self.assertEqual(success.returncode, 0, success.stderr)
            self.assertIn('user_version=13', success.stdout)

            conn = sqlite3.connect(database)
            conn.execute('PRAGMA user_version = 99')
            conn.commit()
            conn.close()
            failure = subprocess.run(
                [sys.executable, 'migrate_database.py', '--database', str(database)],
                cwd=root, capture_output=True, text=True, encoding='utf-8', check=False,
            )
            self.assertNotEqual(failure.returncode, 0)
            self.assertIn('newer than supported', failure.stderr)


if __name__ == '__main__':
    unittest.main()
