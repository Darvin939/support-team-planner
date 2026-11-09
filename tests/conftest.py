"""Select test storage explicitly; never inherit the working database by default."""
import os
import tempfile
from pathlib import Path

import pytest

from backend import settings as _settings

_TEST_ROOT = tempfile.TemporaryDirectory(prefix='support-planner-tests-')
_MODE = os.environ.get('SUPPORT_PLANNER_TEST_BACKEND', 'sqlite')
os.environ['PYTHONUTF8'] = '1'
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['SUPPORT_PLANNER_SKIP_DOTENV'] = '1'
if _MODE == 'postgresql':
    test_url = os.environ.get('SUPPORT_PLANNER_TEST_DATABASE_URL')
    if not test_url:
        raise pytest.UsageError('PostgreSQL tests require a separate SUPPORT_PLANNER_TEST_DATABASE_URL; it will be cleared')
    os.environ['SUPPORT_PLANNER_DATABASE_URL'] = test_url
elif _MODE == 'sqlite':
    os.environ.pop('SUPPORT_PLANNER_DATABASE_URL', None)
    os.environ['SUPPORT_PLANNER_DB_PATH'] = str(Path(_TEST_ROOT.name) / 'default.db')
else:
    raise pytest.UsageError('SUPPORT_PLANNER_TEST_BACKEND must be sqlite or postgresql')


def pytest_configure(config):
    config.addinivalue_line('markers', 'postgresql: requires the explicitly selected PostgreSQL test database')


def pytest_collection_modifyitems(items):
    for item in items:
        if 'postgresql' in item.keywords and _MODE != 'postgresql':
            item.add_marker(pytest.mark.skip(reason='PostgreSQL matrix run required'))
        if _MODE == 'postgresql' and item.path.name not in ('test_storage_contract.py', 'test_postgresql_integration.py'):
            source = item.path.read_text(encoding='utf-8')
            if 'sqlite3' in source or 'sqlite_backend.DB_PATH' in source:
                item.add_marker(pytest.mark.skip(reason='Legacy SQLite fixture; shared contracts run in test_storage_contract.py'))


@pytest.fixture
def storage(tmp_path, monkeypatch):
    from backend import db
    from backend.db.connection import backend
    if backend.name == 'sqlite':
        from backend.db import sqlite
        monkeypatch.setattr(sqlite, 'DB_PATH', str(tmp_path / 'matrix.db'))
        db.init_db()
    else:
        from backend.db.postgresql import PostgreSQLBackend, database_identity
        from backend.db.postgresql_migrations import run_migrations
        from backend.db.schema_manifest import TABLES
        migration = PostgreSQLBackend(os.environ.get('SUPPORT_PLANNER_TEST_MIGRATION_URL', os.environ['SUPPORT_PLANNER_TEST_DATABASE_URL']))
        conn = migration.connect()
        try:
            migration.setup_connection(conn)
            runtime = backend.connect()
            try:
                backend.setup_connection(runtime)
                if database_identity(runtime) != database_identity(conn):
                    raise RuntimeError('Test runtime and migration URLs identify different databases; no cleanup performed')
            finally:
                backend.close(runtime)
            conn.rollback()
            run_migrations(conn, migration, schema_only=True)
            with migration.migration_lock(conn):
                migration.begin_write(conn)
                conn.execute('TRUNCATE TABLE ' + ', '.join('ONLY public."%s"' % table for table in TABLES) + ' RESTART IDENTITY RESTRICT')
                conn.commit()
        finally:
            migration.close(conn)
        from backend.auth import hash_password
        db.create_user(None, 'Администратор', role='admin', login='admin', password_hash=hash_password('q12345678'), is_assignee=False)
    yield backend


def pytest_unconfigure(config):
    _TEST_ROOT.cleanup()
