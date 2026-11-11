import os
import subprocess
import sys
from pathlib import Path

import pytest

from backend.db.postgresql import Row, StorageError, validate_url
from backend.db.search import casefold, fuzzy_word_in, task_matches
from backend.db.sqlite import SQLiteBackend
from scripts.import_sqlite_to_postgres import TransferError, prepare_source, table_digest, validate_source

ROOT = Path(__file__).resolve().parents[1]


def subprocess_env():
    env = os.environ.copy()
    env['PYTHONPATH'] = str(ROOT)
    env['PYTHONUTF8'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    return env


@pytest.mark.parametrize('url', ['', 'sqlite:///tmp.db', 'postgresql://[invalid', 'secret-password'])
def test_configuration_errors_never_echo_dsn(url, tmp_path):
    env = subprocess_env()
    env['SUPPORT_PLANNER_DATABASE_URL'] = url
    result = subprocess.run([sys.executable, '-c', 'from backend.db.connection import backend'], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert 'Invalid SUPPORT_PLANNER_DATABASE_URL' in result.stderr
    assert 'secret-password' not in result.stderr
    assert not (tmp_path / 'database.db').exists()


def test_selection_default_priority_and_failed_connection(tmp_path):
    env = subprocess_env()
    env.pop('SUPPORT_PLANNER_DATABASE_URL', None)
    env['SUPPORT_PLANNER_DB_PATH'] = str(tmp_path / 'never-open.db')
    script = 'from backend.db.connection import backend; print(backend.name)'
    assert subprocess.run([sys.executable, '-c', script], cwd=tmp_path, env=env, capture_output=True, text=True).stdout.strip() == 'sqlite'
    env['SUPPORT_PLANNER_DATABASE_URL'] = 'postgresql://reader:sentinel-test-password@127.0.0.1:1/test?connect_timeout=1'
    assert subprocess.run([sys.executable, '-c', script], cwd=tmp_path, env=env, capture_output=True, text=True).stdout.strip() == 'postgresql'
    script += '; backend.connect()'
    result = subprocess.run([sys.executable, '-c', script], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert 'sentinel-test-password' not in result.stderr + result.stdout
    assert 'PostgreSQL operation failed' in result.stderr
    assert not (tmp_path / 'never-open.db').exists()


def test_explicit_sqlite_cli_ignores_postgresql_settings(tmp_path):
    env = subprocess_env()
    env['SUPPORT_PLANNER_DATABASE_URL'] = 'invalid-secret-password'
    env['SUPPORT_PLANNER_DATABASE_SCHEMA'] = ''
    result = subprocess.run([sys.executable, '-m', 'scripts.migrate_database', '--database', str(tmp_path / 'explicit.db')], cwd=ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert 'user_version=15' in result.stdout


def test_compatible_row_and_search_semantics():
    row = Row(('id', 'name'), (2, 'Ёж'))
    assert row[0] == row['id'] == 2
    assert dict(row) == {'id': 2, 'name': 'Ёж'}
    assert tuple(row) == (2, 'Ёж')
    assert casefold('Straße') == 'strasse'
    assert fuzzy_word_in('ОШИБКА', 'ошипка')
    assert not fuzzy_word_in('Аб', 'ав')
    assert not fuzzy_word_in(None, 'слово')
    assert task_matches('Ошибка', 'Биллинга', 'ошипка биллинг')
    assert not task_matches('Ошибка', '', 'ошибка биллинг')


def test_fresh_wal_snapshots_preserve_source_and_include_new_commits(tmp_path):
    source = tmp_path / 'source.db'
    backend = SQLiteBackend(str(source))
    conn = backend.connect()
    backend.setup_connection(conn)
    backend.init_schema(conn)
    conn.execute("INSERT INTO teams (name) VALUES ('First')")
    conn.commit()
    report1, report2 = {}, {}
    first = prepare_source(source, report1)
    try:
        conn.execute("INSERT INTO teams (name) VALUES ('Second')")
        conn.commit()
        second = prepare_source(source, report2)
        try:
            assert first.execute('SELECT COUNT(*) FROM teams').fetchone()[0] == 1
            assert second.execute('SELECT COUNT(*) FROM teams').fetchone()[0] == 2
            assert report1['snapshot']['path'] != report2['snapshot']['path']
            assert report1['working_copy'] != report1['snapshot']['path']
            assert conn.execute('SELECT COUNT(*) FROM teams').fetchone()[0] == 2
        finally:
            second.close()
    finally:
        first.close()
        conn.close()


def test_source_rejects_nul_and_wrong_storage_type_without_echoing_values(tmp_path):
    backend = SQLiteBackend(str(tmp_path / 'source.db'))
    conn = backend.connect()
    backend.setup_connection(conn)
    backend.init_schema(conn)
    conn.execute('UPDATE users SET password_hash = ?', ('secret-hash\x00data',))
    conn.commit()
    with pytest.raises(TransferError) as error:
        validate_source(conn)
    assert 'users' in str(error.value) and 'secret-hash' not in str(error.value)
    conn.execute("UPDATE users SET password_hash = NULL, is_assignee = 'not-an-integer'")
    conn.commit()
    with pytest.raises(TransferError, match='is_assignee'):
        validate_source(conn)
    conn.close()


def test_transfer_source_future_version_fails_before_target_connection(tmp_path):
    from unittest.mock import patch
    from scripts.import_sqlite_to_postgres import transfer
    path = tmp_path / 'future.db'
    backend = SQLiteBackend(str(path))
    conn = backend.connect()
    backend.setup_connection(conn)
    backend.init_schema(conn)
    conn.execute('PRAGMA user_version=999')
    conn.close()
    report = {}
    with patch('backend.db.postgresql.PostgreSQLBackend.connect', side_effect=AssertionError('target was touched')):
        with pytest.raises(RuntimeError, match='newer|Future|future'):
            transfer(path, replace=True, report=report)
    assert report['commit'] == 'rolled_back'
    conn = backend.connect()
    assert conn.execute('PRAGMA user_version').fetchone()[0] == 999
    conn.close()


def test_schema_manifest_covers_complete_sqlite_v15(tmp_path):
    from backend.db.schema_manifest import TABLES
    backend = SQLiteBackend(str(tmp_path / 'manifest.db'))
    conn = backend.connect()
    backend.setup_connection(conn)
    backend.init_schema(conn)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert tables - {'sqlite_sequence', 'schema_migrations'} == set(TABLES)
    for table, spec in TABLES.items():
        assert [r[1] for r in conn.execute('PRAGMA table_info("%s")' % table)] == [c[0] for c in spec['columns']]
    conn.close()


def test_old_source_migrates_only_working_copy_without_bootstrap(tmp_path):
    path = tmp_path / 'old.db'
    backend = SQLiteBackend(str(path))
    conn = backend.connect()
    backend.setup_connection(conn)
    backend.init_schema(conn)
    conn.execute('DELETE FROM users')
    conn.execute('DELETE FROM schema_migrations WHERE version > 6')
    conn.execute('PRAGMA user_version=6')
    conn.commit()
    before = list(conn.iterdump())
    report = {}
    working = prepare_source(path, report)
    try:
        assert working.execute('PRAGMA user_version').fetchone()[0] == 15
        assert working.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0
        assert list(conn.iterdump()) == before
        assert report['source_version'] == 15
    finally:
        working.close()
        conn.close()


@pytest.mark.parametrize('damage', ['file', 'unique', 'foreign_key'])
def test_damaged_source_fails_before_target_is_opened(tmp_path, damage):
    import sqlite3
    from unittest.mock import patch
    from scripts.import_sqlite_to_postgres import transfer
    path = tmp_path / 'damaged.db'
    if damage == 'file':
        path.write_bytes(b'not a SQLite database')
    else:
        backend = SQLiteBackend(str(path))
        conn = backend.connect()
        backend.setup_connection(conn)
        backend.init_schema(conn)
        if damage == 'unique':
            conn.execute('DROP INDEX idx_users_login')
            conn.execute("INSERT INTO users (first_name,login) VALUES ('Duplicate','admin')")
        else:
            conn.execute('DROP TABLE team_blocks')
            conn.execute('CREATE TABLE team_blocks (id INTEGER PRIMARY KEY AUTOINCREMENT, team_id INTEGER NOT NULL, block_name TEXT NOT NULL, schedule_offset INTEGER NOT NULL DEFAULT 0)')
            conn.execute("INSERT INTO team_blocks (team_id,block_name) VALUES (999,'Orphan')")
        conn.commit()
        conn.close()
    original = path.read_bytes()
    with patch('backend.db.postgresql.PostgreSQLBackend.connect', side_effect=AssertionError('target opened')):
        with pytest.raises((TransferError, sqlite3.DatabaseError)):
            transfer(path, replace=True)
    assert path.read_bytes() == original
