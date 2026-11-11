"""Destructive integration tests, enabled only by the explicit PostgreSQL test URL."""
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from unittest.mock import patch
from uuid import uuid4

import pytest

from backend import db
from backend.db.postgresql import PostgreSQLBackend, SchemaConfigurationError, StorageError
from backend.db.postgresql_migrations import Migration, check_schema, journal_exists, migrations, run_migrations, validate_journal
from backend.db.schema_manifest import TABLES
from backend.db.sqlite import SQLiteBackend
from scripts import import_sqlite_to_postgres as importer

pytestmark = pytest.mark.postgresql


@pytest.fixture
def target(storage, monkeypatch):
    url = os.environ.get('SUPPORT_PLANNER_TEST_MIGRATION_URL', os.environ['SUPPORT_PLANNER_TEST_DATABASE_URL'])
    monkeypatch.setenv('SUPPORT_PLANNER_DATABASE_URL', url)
    backend = PostgreSQLBackend(url)
    conn = backend.connect()
    try:
        backend.setup_connection(conn)
        yield backend, conn
    finally:
        backend.close(conn)


@pytest.fixture
def source(tmp_path):
    path = tmp_path / 'source.db'
    backend = SQLiteBackend(str(path))
    conn = backend.connect()
    backend.setup_connection(conn)
    backend.init_schema(conn)
    statements = [
        "INSERT INTO teams (id,name) VALUES (10,'Источник')",
        "INSERT INTO segments (id,name) VALUES (10,'Сегмент')",
        "INSERT INTO blocks (id,name) VALUES (10,'БЛОК')",
        "INSERT INTO team_blocks (id,team_id,block_name) VALUES (10,10,'БЛОК')",
        "INSERT INTO block_templates (id,name,segment_id) VALUES (10,'Шаблон',10)",
        "INSERT INTO template_blocks (id,template_id,block_id) VALUES (10,10,10)",
        "INSERT INTO team_templates VALUES (10,10)",
        "INSERT INTO user_team_access VALUES (1,10)",
        "INSERT INTO freeze_days (id,date) VALUES (10,'2026-11-09')",
        "INSERT INTO tasks (id,team_id,segment_id,name,completion_template_id) VALUES (100,10,10,'Работа',10),(200,10,10,'Удалённая',10)",
        "UPDATE tasks SET is_deleted=1,task_status='done',completed_at='2026-11-01 12:00:00' WHERE id=200",
        "INSERT INTO assignments (id,task_id,date,block,status) VALUES (500,100,'2026-11-09','БЛОК','success')",
        "INSERT INTO task_dependencies VALUES (200,100)",
        "INSERT INTO task_history (id,task_id,action,new_value,changed_by_user_id) VALUES (900,100,'create','снимок',1)",
        "INSERT INTO assignment_history (id,assignment_id,task_id,date,action,changed_by_user_id) VALUES (800,500,100,'2026-11-09','create',1)",
        "INSERT INTO user_new_task_notification_seen_events VALUES (1,900,'2026-11-09 12:00:00')",
        "INSERT INTO application_metadata VALUES (1,'test','test-build','2026-11-09T12:00:00Z')",
        "INSERT INTO user_release_change_log_seen VALUES (1,'test','2026-11-09T12:00:00Z')",
    ]
    for statement in statements:
        conn.execute(statement)
    conn.commit()
    yield path, conn
    conn.close()


def empty(conn):
    conn.execute('TRUNCATE TABLE ' + ', '.join('ONLY %s' % conn.qualified_name(table) for table in TABLES) + ' RESTART IDENTITY RESTRICT')
    conn.commit()


def snapshot(conn):
    data = {table: importer.table_digest(conn, table, spec, postgres=True) for table, spec in TABLES.items()}
    sequences = {}
    from psycopg import sql
    for table, spec in TABLES.items():
        if spec['identity']:
            row = conn.execute('''SELECT n.nspname,c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE c.oid=pg_get_serial_sequence(%s,'id')::regclass''', (conn.qualified_name(table),)).fetchone()
            values = conn.execute(sql.SQL('SELECT last_value,is_called FROM {}').format(sql.Identifier(row[0],row[1]))).fetchone()
            sequences[table] = (values[0],values[1])
    conn.rollback()
    return data, sequences


def test_baseline_manifest_and_runtime_validation(target):
    backend, conn = target
    check_schema(conn)
    assert len(TABLES) == 19
    assert validate_journal(conn, migrations(), require_current=True) == 1
    before = conn.execute('SELECT checksum FROM schema_migrations').fetchone()[0]
    conn.rollback()
    run_migrations(conn, backend, schema_only=True)
    assert conn.execute('SELECT checksum FROM schema_migrations').fetchone()[0] == before
    conn.execute("UPDATE schema_migrations SET checksum='wrong'")
    with pytest.raises(RuntimeError, match='mismatch'):
        check_schema(conn)
    conn.rollback()
    check_schema(conn)


def test_failed_step_and_two_concurrent_migrators(target):
    backend, conn = target
    conn.rollback()
    rejected = Migration(2, 'rejected', 'CREATE TABLE migration_probe (id bigint)', lambda connection: (_ for _ in ()).throw(RuntimeError('postcondition')))
    with pytest.raises(RuntimeError, match='postcondition'):
        run_migrations(conn, backend, [*migrations(), rejected], schema_only=True)
    assert conn.execute("SELECT to_regclass('migration_probe')").fetchone()[0] is None
    conn.rollback()
    step = Migration(2, 'concurrent-probe', 'CREATE TABLE migration_probe (id bigint)')
    def migrate():
        other = backend.connect()
        try:
            backend.setup_connection(other)
            run_migrations(other, backend, [*migrations(), step], schema_only=True)
        finally:
            backend.close(other)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _: migrate(), range(2)))
        assert conn.execute('SELECT COUNT(*) FROM schema_migrations WHERE version=2').fetchone()[0] == 1
    finally:
        conn.rollback()
        conn.execute('DROP TABLE IF EXISTS migration_probe')
        conn.execute('DELETE FROM schema_migrations WHERE version=2')
        conn.commit()


def test_import_repeat_replace_and_dry_run(target, source):
    backend, conn = target
    path, sqlite = source
    empty(conn)
    first = importer.transfer(path)
    assert first['commit'] == 'committed'
    assert len(first['verification']) == 19
    with pytest.raises(importer.TransferError, match='not empty'):
        importer.transfer(path)
    conn.execute("UPDATE users SET password_hash='temporary-test-password'")
    conn.execute("INSERT INTO teams(id,name) VALUES (99999,'Only in PostgreSQL')")
    conn.execute("DELETE FROM freeze_days")
    conn.commit()
    sqlite.execute("UPDATE teams SET name='Новый снимок'")
    sqlite.execute("DELETE FROM freeze_days")
    sqlite.commit()
    before = snapshot(conn)
    dry = importer.transfer(path, replace=True, dry_run=True)
    assert dry['commit'] == 'dry_run'
    assert dry['before_counts']['teams'] == 2
    assert snapshot(conn) == before
    second = importer.transfer(path, replace=True)
    assert second['commit'] == 'committed'
    assert first['snapshot']['path'] != second['snapshot']['path']
    assert conn.execute('SELECT name FROM teams').fetchone()[0] == 'Новый снимок'
    conn.rollback()
    assert db.create_team('After import') == 11
    assert not db.get_all_freeze_days()


@pytest.mark.parametrize('stage', ['load_table', 'verify_tables', 'restart_sequences'])
def test_replace_fault_restores_previous_data_and_sequences(target, source, monkeypatch, stage):
    _, conn = target
    path, _ = source
    db.create_team('Previous data')
    before = snapshot(conn)
    original = getattr(importer, stage)
    calls = []
    def fault(*args, **kwargs):
        original(*args, **kwargs)
        calls.append(1)
        raise RuntimeError('injected failure after ' + stage)
    monkeypatch.setattr(importer, stage, fault)
    report = {}
    with pytest.raises(RuntimeError, match='injected'):
        importer.transfer(path, replace=True, report=report)
    assert calls and report['commit'] == 'rolled_back'
    assert snapshot(conn) == before


def test_external_fk_and_unrelated_table_preservation(target, source):
    _, conn = target
    path, _ = source
    conn.execute('CREATE TABLE unrelated_probe (id bigint PRIMARY KEY)')
    conn.execute('INSERT INTO unrelated_probe VALUES (42)')
    conn.commit()
    try:
        importer.transfer(path, replace=True)
        assert conn.execute('SELECT id FROM unrelated_probe').fetchone()[0] == 42
        conn.rollback()
        conn.execute('ALTER TABLE unrelated_probe ADD COLUMN user_id bigint REFERENCES users(id)')
        conn.commit()
        before = snapshot(conn)
        with pytest.raises(importer.TransferError, match='external dependencies'):
            importer.transfer(path, replace=True)
        assert snapshot(conn) == before
    finally:
        conn.rollback()
        conn.execute('DROP TABLE IF EXISTS unrelated_probe')
        conn.commit()


def test_lost_commit_acknowledgement_is_reported_unknown(target, source, monkeypatch):
    from backend.db.postgresql import Connection
    path, _ = source
    report = {}
    commit = Connection.commit
    calls = []
    def lose_ack(connection):
        commit(connection)
        if report.get('commit') == 'unknown':
            calls.append(1)
            raise StorageError('connection lost')
    monkeypatch.setattr(Connection, 'commit', lose_ack)
    with pytest.raises(StorageError):
        importer.transfer(path, replace=True, report=report)
    assert report['commit'] == 'unknown'
    assert len(calls) == 1


@contextmanager
def isolated_schema(target, suffix=''):
    """Only test infrastructure creates schemas, inside the explicit test DB."""
    from psycopg import sql
    owner, admin = target
    name = 'schema_test_' + uuid4().hex[:16] + suffix
    admin.rollback()
    admin.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(name)))
    admin.commit()
    backend = PostgreSQLBackend(owner.url, schema=name)
    conn = None
    try:
        conn = backend.connect()
        backend.setup_connection(conn)
        yield backend, conn
    finally:
        if conn is not None:
            backend.close(conn)
        admin.rollback()
        admin.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(name)))
        admin.commit()


@pytest.mark.parametrize('suffix', ['', '-Mixed"100%s'])
def test_selected_schema_bootstrap_and_no_journal_fallback(target, suffix):
    with isolated_schema(target, suffix) as (backend, conn):
        # The base test schema already has a journal and tables.
        assert not journal_exists(conn)
        with pytest.raises(RuntimeError, match='schema missing'):
            check_schema(conn)
        conn.rollback()
        run_migrations(conn, backend)
        check_schema(conn)
        assert conn.execute('SELECT current_schema()').fetchone()[0] == backend.schema
        assert conn.execute('SELECT login FROM users').fetchone()[0] == 'admin'
        conn.execute("UPDATE users SET password_hash='preserve-this-password'")
        conn.commit()
        run_migrations(conn, backend)
        assert conn.execute('SELECT password_hash FROM users').fetchone()[0] == 'preserve-this-password'
        assert conn.execute('SELECT checksum FROM schema_migrations').fetchone()[0] == migrations()[0].checksum


@pytest.mark.parametrize('suffix', ['', '-Mixed"100%s'])
def test_import_and_replace_are_isolated_to_selected_schema(target, source, monkeypatch, suffix):
    _, base = target
    path, sqlite = source
    before = snapshot(base)
    with isolated_schema(target, suffix) as (backend, conn):
        monkeypatch.setenv('SUPPORT_PLANNER_DATABASE_SCHEMA', backend.schema)
        # A dry-run must not create even the journal in an existing empty schema.
        dry = importer.transfer(path, dry_run=True)
        assert dry['target']['schema'] == backend.schema
        assert not journal_exists(conn)
        conn.rollback()
        first = importer.transfer(path)
        assert first['commit'] == 'committed'
        assert first['target']['schema'] == backend.schema
        assert importer.verify_tables(sqlite, conn) == first['verification']
        conn.rollback()
        assert backend.insert_id(conn, "INSERT INTO teams (name) VALUES (%s)", ('After import',)) == 11
        conn.commit()
        journal = tuple(conn.execute('SELECT version, name, checksum FROM schema_migrations').fetchone())
        conn.rollback()
        sqlite.execute("UPDATE teams SET name='Second snapshot'")
        sqlite.commit()
        imported = snapshot(conn)
        assert importer.transfer(path, replace=True, dry_run=True)['commit'] == 'dry_run'
        assert snapshot(conn) == imported
        second = importer.transfer(path, replace=True)
        assert second['commit'] == 'committed'
        assert conn.execute('SELECT name FROM teams').fetchone()[0] == 'Second snapshot'
        assert tuple(conn.execute('SELECT version, name, checksum FROM schema_migrations').fetchone()) == journal
        conn.rollback()
        assert snapshot(base) == before


def test_cross_schema_foreign_keys_refuse_replacement(target, source, monkeypatch):
    path, _ = source
    with isolated_schema(target) as (backend, conn):
        run_migrations(conn, backend)
        monkeypatch.setenv('SUPPORT_PLANNER_DATABASE_SCHEMA', backend.schema)
        with isolated_schema(target) as (_, outside):
            outside.execute('CREATE TABLE external_reference (user_id bigint REFERENCES %s(id))' % conn.qualified_name('users'))
            outside.commit()
            before = snapshot(conn)
            with pytest.raises(importer.TransferError, match='external dependencies'):
                importer.transfer(path, replace=True)
            assert snapshot(conn) == before


def test_missing_schema_cli_does_not_create_it(target, source, monkeypatch, capsys):
    from scripts.migrate_database import main as migrate
    _, conn = target
    schema = 'missing_' + uuid4().hex
    monkeypatch.setenv('SUPPORT_PLANNER_DATABASE_SCHEMA', schema)
    assert migrate(['--postgresql', '--schema-only']) == 1
    assert schema in capsys.readouterr().err
    assert importer.main(['--source', str(source[0]), '--dry-run']) == 1
    assert schema in capsys.readouterr().err
    assert conn.execute('SELECT 1 FROM pg_namespace WHERE nspname=%s', (schema,)).fetchone() is None


def test_runtime_usage_required_and_runtime_cannot_perform_ddl(target):
    from psycopg import sql
    with isolated_schema(target) as (migration, admin):
        run_migrations(admin, migration)
        runtime = PostgreSQLBackend(os.environ['SUPPORT_PLANNER_TEST_DATABASE_URL'], schema=migration.schema)
        conn = runtime.connect()
        try:
            role = conn.execute('SELECT current_user').fetchone()[0]
            owner = admin.execute('SELECT current_user').fetchone()[0]
            if role == owner or conn.execute('SELECT rolsuper FROM pg_roles WHERE rolname=current_user').fetchone()[0]:
                pytest.skip('Runtime permissions require a separate non-superuser test runtime role')
            conn.rollback()
            with pytest.raises(SchemaConfigurationError, match='USAGE'):
                runtime.setup_connection(conn)
            conn.rollback()
            admin.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO {}').format(sql.Identifier(migration.schema), sql.Identifier(role)))
            admin.execute(sql.SQL('GRANT SELECT ON ALL TABLES IN SCHEMA {} TO {}').format(sql.Identifier(migration.schema), sql.Identifier(role)))
            admin.execute(sql.SQL('GRANT SELECT, USAGE ON ALL SEQUENCES IN SCHEMA {} TO {}').format(sql.Identifier(migration.schema), sql.Identifier(role)))
            for table in TABLES:
                admin.execute(sql.SQL('GRANT INSERT, UPDATE, DELETE ON {} TO {}').format(sql.Identifier(migration.schema, table), sql.Identifier(role)))
            admin.commit()
            runtime.setup_connection(conn)
            check_schema(conn)
            assert runtime.insert_id(conn, 'INSERT INTO teams (name) VALUES (%s)', ('Runtime insert',))
            conn.commit()
            with pytest.raises(StorageError):
                conn.execute('CREATE TABLE forbidden_probe (id bigint)')
            conn.rollback()
            with pytest.raises(StorageError):
                conn.execute("UPDATE schema_migrations SET checksum='forbidden'")
            conn.rollback()
            check_schema(conn)
        finally:
            runtime.close(conn)
