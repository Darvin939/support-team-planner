"""
Тест PostgreSQL backend.

Секция 1 — unit-тесты без реального сервера (мок psycopg2).
Секция 2 — интеграционный тест с живым PG (пропускается если недоступен).

Запуск: python test_pg.py
"""
import sys
import unittest
from unittest.mock import MagicMock, patch

from db_postgres import _adapt_sql, _PgConnectionWrapper, _PgCursor, PostgresBackend


# ── unit-тесты ──────────────────────────────────────────────────────────────


class TestAdaptSql(unittest.TestCase):

    def test_placeholder(self):
        self.assertEqual(_adapt_sql('SELECT * FROM t WHERE id = ?'), 'SELECT * FROM t WHERE id = %s')

    def test_multiple_placeholders(self):
        sql = 'INSERT INTO t (a, b) VALUES (?, ?)'
        self.assertEqual(_adapt_sql(sql), 'INSERT INTO t (a, b) VALUES (%s, %s)')

    def test_insert_or_ignore(self):
        sql = 'INSERT OR IGNORE INTO task_dependencies (task_id, dep_id) VALUES (?, ?)'
        got = _adapt_sql(sql)
        self.assertIn('ON CONFLICT DO NOTHING', got)
        self.assertNotIn('OR IGNORE', got)
        self.assertIn('%s', got)

    def test_no_change_needed(self):
        sql = "SELECT name FROM teams WHERE name LIKE %s"
        self.assertEqual(_adapt_sql(sql), sql)

    def test_insert_or_ignore_case(self):
        sql = 'insert or ignore into freeze_days (date) values (?)'
        got = _adapt_sql(sql)
        self.assertIn('ON CONFLICT DO NOTHING', got)
        self.assertIn('%s', got)


class TestPgConnectionWrapper(unittest.TestCase):

    def _make_conn(self):
        fake_cur = MagicMock()
        fake_cur.fetchone.return_value = {'id': 42}
        fake_cur.fetchall.return_value = [{'id': 1}, {'id': 2}]

        fake_pg_conn = MagicMock()
        fake_pg_conn.cursor.return_value = fake_cur

        wrapper = _PgConnectionWrapper(fake_pg_conn)
        return wrapper, fake_pg_conn, fake_cur

    def test_execute_adapts_placeholder(self):
        wrapper, pg_conn, cur = self._make_conn()
        wrapper.execute('SELECT 1 WHERE id = ?', (5,))
        args = cur.execute.call_args
        self.assertIn('%s', args[0][0])
        self.assertNotIn('?', args[0][0])

    def test_execute_adapts_insert_or_ignore(self):
        wrapper, pg_conn, cur = self._make_conn()
        wrapper.execute('INSERT OR IGNORE INTO t (a) VALUES (?)', ('x',))
        sql_used = cur.execute.call_args[0][0]
        self.assertIn('ON CONFLICT DO NOTHING', sql_used)

    def test_execute_returns_pg_cursor(self):
        wrapper, pg_conn, cur = self._make_conn()
        result = wrapper.execute('SELECT 1')
        self.assertIsInstance(result, _PgCursor)

    def test_fetchone_delegates(self):
        wrapper, pg_conn, cur = self._make_conn()
        pg_cur = wrapper.execute('SELECT 1')
        row = pg_cur.fetchone()
        self.assertEqual(row, {'id': 42})

    def test_commit_delegates(self):
        wrapper, pg_conn, cur = self._make_conn()
        wrapper.commit()
        pg_conn.commit.assert_called_once()

    def test_close_delegates(self):
        wrapper, pg_conn, cur = self._make_conn()
        wrapper.close()
        pg_conn.close.assert_called_once()


class TestPostgresBackendInterface(unittest.TestCase):

    def _make_backend(self, **kwargs):
        return PostgresBackend(**kwargs)

    def test_db_error_is_psycopg2_error(self):
        import psycopg2
        b = self._make_backend()
        self.assertIs(b.db_error, psycopg2.Error)

    def test_duplicate_error_is_unique_violation(self):
        import psycopg2.errors
        b = self._make_backend()
        self.assertIs(b.duplicate_error, psycopg2.errors.UniqueViolation)

    @patch('db_postgres.psycopg2.connect')
    def test_connect_passes_kwargs(self, mock_connect):
        mock_connect.return_value = MagicMock()
        b = PostgresBackend(host='myhost', dbname='mydb', user='u')
        b.connect()
        mock_connect.assert_called_once_with(host='myhost', dbname='mydb', user='u')

    @patch('db_postgres.psycopg2.connect')
    def test_connect_no_kwargs_calls_connect_without_args(self, mock_connect):
        mock_connect.return_value = MagicMock()
        b = PostgresBackend()
        b.connect()
        mock_connect.assert_called_once_with()

    def test_last_insert_id(self):
        b = PostgresBackend()
        fake_cur = MagicMock()
        fake_cur.fetchone.return_value = [99]
        pg_cur = _PgCursor(fake_cur)
        result = b.last_insert_id(pg_cur)
        fake_cur.execute.assert_called_once_with("SELECT lastval()")
        self.assertEqual(result, 99)

    def test_setup_connection_is_noop(self):
        b = PostgresBackend()
        conn = MagicMock()
        b.setup_connection(conn)
        conn.execute.assert_not_called()

    @patch('db_postgres.psycopg2.connect')
    def test_init_schema_runs_all_stmts(self, mock_connect):
        b = PostgresBackend()
        conn = MagicMock()
        b.init_schema(conn)
        # fuzzy_word_in + количество DDL-стейтментов
        from db_postgres import _PG_SCHEMA_STMTS
        self.assertEqual(conn.execute.call_count, 1 + len(_PG_SCHEMA_STMTS))


# ── интеграционный тест ──────────────────────────────────────────────────────

PG_PARAMS = dict(host='localhost', dbname='postgres', user='postgres', connect_timeout=3)
TEST_DB = 'support_planner_test'


def _try_live_test():
    import psycopg2
    import database

    # Проверяем доступность PG
    try:
        admin = psycopg2.connect(**PG_PARAMS)
    except psycopg2.OperationalError as e:
        print(f'\n[SKIP] PostgreSQL недоступен: {e}')
        return

    # Создаём тестовую БД
    admin.autocommit = True
    cur = admin.cursor()
    cur.execute(f'DROP DATABASE IF EXISTS {TEST_DB}')
    cur.execute(f'CREATE DATABASE {TEST_DB}')
    admin.close()

    try:
        from db_postgres import PostgresBackend
        pg = PostgresBackend(host='localhost', dbname=TEST_DB, user='postgres')

        # Временно переключаем бэкенд
        original = database._backend
        database._backend = pg

        # init_schema
        database.init_db()

        # Создаём команду
        team_id = database.create_team('PG-команда', [{'name': 'Б1', 'shift_days': 0}])
        assert isinstance(team_id, int) and team_id > 0, f'team_id={team_id}'

        # Создаём сотрудника
        emp_id = database.create_employee('Иванов', 'Иван', 'Иванович')
        assert isinstance(emp_id, int) and emp_id > 0, f'emp_id={emp_id}'

        # Создаём задачу
        task_id = int(database.create_or_update_task(None, team_id, 'Тест задача', 'Описание', 'high'))
        assert isinstance(task_id, int) and task_id > 0, f'task_id={task_id}'

        # Пагинация задач
        tasks = database.get_tasks_by_team(team_id)
        assert len(tasks) == 1
        assert tasks[0]['name'] == 'Тест задача'

        # Fuzzy search
        found = database.get_tasks_by_team(team_id, search='задаче')  # опечатка
        assert len(found) == 1, f'Fuzzy search не нашёл: {found}'

        # Назначение
        database.create_or_update_assignment(None, task_id, '2026-07-01', 'Б1', 'new', emp_id, None)
        assignments = database.get_assignments_by_team_in_period(team_id, '2026-07-01', '2026-07-01')
        assert len(assignments) == 1

        # INSERT OR IGNORE (через set_task_dependencies)
        task_id2 = int(database.create_or_update_task(None, team_id, 'Задача 2', None, 'low'))
        database.set_task_dependencies(task_id2, [task_id])
        database.set_task_dependencies(task_id2, [task_id])  # повтор — не должен упасть

        print('\n[OK] Интеграционный тест PostgreSQL прошёл успешно')
        print(f'     team_id={team_id}, task_id={task_id}, emp_id={emp_id}')

    finally:
        database._backend = original
        # Удаляем тестовую БД
        admin2 = psycopg2.connect(**PG_PARAMS)
        admin2.autocommit = True
        admin2.cursor().execute(f'DROP DATABASE IF EXISTS {TEST_DB}')
        admin2.close()
        print(f'     Тестовая БД {TEST_DB!r} удалена')


if __name__ == '__main__':
    print('=== Unit-тесты ===')
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [TestAdaptSql, TestPgConnectionWrapper, TestPostgresBackendInterface]:
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print('\n=== Интеграционный тест (требует живой PostgreSQL) ===')
    _try_live_test()

    sys.exit(0 if result.wasSuccessful() else 1)
