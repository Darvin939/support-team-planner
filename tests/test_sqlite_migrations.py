import sqlite3
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
            self.assertEqual(current_version(conn), 9)
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
            self.assertEqual(current_version(conn), 9)
            self.assertEqual(conn.execute('SELECT name FROM tasks WHERE id = 3').fetchone()[0], 'Legacy task')
            self.assertEqual(conn.execute('SELECT user_id FROM assignments WHERE id = 4').fetchone()[0], 2)
            task_columns = {row[1] for row in conn.execute('PRAGMA table_info(tasks)')}
            self.assertTrue({
                'priority', 'criticality', 'segment_id', 'completed_at', 'completion_template_id', 'psi_status',
            } <= task_columns)
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


if __name__ == '__main__':
    unittest.main()
