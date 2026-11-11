"""Schema configuration and SQL composition checks without a PostgreSQL server."""
import runpy
from pathlib import Path
from unittest.mock import Mock

import pytest

from backend.db.postgresql import Connection, PostgreSQLBackend, SchemaConfigurationError, validate_schema
from backend.db.postgresql_migrations import journal_exists, migrations
from backend.db.schema_manifest import TABLES

ROOT = Path(__file__).resolve().parents[1]
URL = 'postgresql://schema_test@127.0.0.1:1/unused'


def test_schema_default_override_and_connection_keep_one_value(monkeypatch):
    monkeypatch.delenv('SUPPORT_PLANNER_DATABASE_SCHEMA', raising=False)
    assert PostgreSQLBackend(URL).schema == 'planner'
    monkeypatch.setenv('SUPPORT_PLANNER_DATABASE_SCHEMA', 'public')
    backend = PostgreSQLBackend(URL)
    monkeypatch.setenv('SUPPORT_PLANNER_DATABASE_SCHEMA', 'changed_later')
    raw = Mock()
    monkeypatch.setattr('psycopg.connect', Mock(return_value=raw))
    conn = backend.connect()
    assert conn.schema == backend.schema == 'public'
    assert PostgreSQLBackend(URL, schema='explicit').schema == 'explicit'


@pytest.mark.parametrize('override', [None, 'environment_schema'])
def test_settings_load_schema_from_dotenv_without_overriding_environment(tmp_path, monkeypatch, override):
    import dotenv
    path = tmp_path / '.env'
    path.write_text('SUPPORT_PLANNER_DATABASE_SCHEMA=file_schema\n', encoding='utf-8')
    # Register the original value for cleanup, including changes made by dotenv.
    monkeypatch.setenv('SUPPORT_PLANNER_DATABASE_SCHEMA', 'temporary')
    if override is None:
        monkeypatch.delenv('SUPPORT_PLANNER_DATABASE_SCHEMA')
    else:
        monkeypatch.setenv('SUPPORT_PLANNER_DATABASE_SCHEMA', override)
    monkeypatch.delenv('SUPPORT_PLANNER_SKIP_DOTENV', raising=False)
    load_dotenv = dotenv.load_dotenv
    monkeypatch.setattr(dotenv, 'load_dotenv', lambda **kwargs: load_dotenv(path, **kwargs))
    runpy.run_path(str(ROOT / 'backend/settings.py'))
    assert PostgreSQLBackend(URL).schema == (override or 'file_schema')


@pytest.mark.parametrize('schema', ['', '   ', '\t', 'a\x00b', 'a' * 64, 'я' * 32, '\ud800', None, 1])
def test_invalid_schema_is_rejected(schema):
    with pytest.raises(SchemaConfigurationError, match='SUPPORT_PLANNER_DATABASE_SCHEMA'):
        validate_schema(schema)


@pytest.mark.parametrize('schema', ['planner', 'public', 'Mixed-Case', 'кавычка"', 'я' * 31, 'x, public', '100%s'])
def test_exact_schema_identifier_is_preserved(schema):
    assert validate_schema(schema) == schema
    conn = Connection(None, schema)
    expected = '"' + schema.replace('"', '""') + '"."users"'
    assert conn.qualified_name('users') == expected
    assert conn.qualified_name('users', parameters=True) == expected.replace('%', '%%')


def test_schema_search_path_is_one_quoted_identifier(monkeypatch):
    schema = 'Planner", public; SELECT 1; --'
    conn = Connection(None, schema)
    execute = Mock()
    execute.return_value.fetchone.side_effect = [(True,), (schema,)]
    monkeypatch.setattr(conn, 'execute', execute)
    monkeypatch.setattr(conn, 'commit', Mock())
    PostgreSQLBackend(URL, schema=schema).setup_connection(conn)
    assert execute.call_args_list[0].args[1] == (schema,)
    path_query = execute.call_args_list[1].args[0].as_string()
    assert path_query == 'SET search_path TO "Planner"", public; SELECT 1; --"'
    conn.commit.assert_called_once()


@pytest.mark.parametrize('access, message', [(None, 'does not exist'), ((False,), 'USAGE')])
def test_missing_or_inaccessible_schema_does_not_run_ddl(monkeypatch, access, message):
    conn = Connection(None, 'not_ready')
    execute = Mock()
    execute.return_value.fetchone.return_value = access
    monkeypatch.setattr(conn, 'execute', execute)
    with pytest.raises(SchemaConfigurationError, match=message):
        PostgreSQLBackend(URL, schema=conn.schema).setup_connection(conn)
    assert execute.call_count == 1
    assert execute.call_args.args[0].startswith('SELECT ')


def test_schema_setup_failure_closes_owned_connection(monkeypatch):
    from backend.db import connection
    raw = Mock()
    conn = Connection(raw, 'missing')
    backend = PostgreSQLBackend(URL, schema=conn.schema)
    monkeypatch.setattr(backend, 'connect', lambda: conn)
    monkeypatch.setattr(connection, 'backend', backend)
    monkeypatch.setattr(conn, 'execute', Mock())
    conn.execute.return_value.fetchone.return_value = None
    with pytest.raises(SchemaConfigurationError, match='missing'):
        connection.get_db_connection()
    raw.close.assert_called_once()


def test_sqlite_selection_ignores_invalid_postgresql_schema(monkeypatch):
    from backend.db.connection import select_backend
    monkeypatch.delenv('SUPPORT_PLANNER_DATABASE_URL', raising=False)
    monkeypatch.setenv('SUPPORT_PLANNER_DATABASE_SCHEMA', '')
    assert select_backend().name == 'sqlite'


@pytest.mark.parametrize('schema', ['planner', 'public', 'Custom"-100%s'])
def test_published_baseline_checksum_and_all_object_references(schema):
    baseline = migrations()[0]
    assert baseline.checksum == '36d4cbfe60a5318bce9ff22d0429685f83d42dd51ad766e58c452033ba6a9ab7'
    conn = Connection(None, schema)
    rendered = baseline.render(baseline.sql, conn)
    assert 'public."' not in rendered
    for table in TABLES:
        assert 'CREATE TABLE ' + conn.qualified_name(table) in rendered
    assert rendered.count('REFERENCES ') == rendered.count('REFERENCES "' + schema.replace('"', '""') + '".')
    assert 'CREATE SCHEMA' not in rendered
    assert baseline.sql == (ROOT / 'backend/db/postgresql_baseline.sql').read_text(encoding='utf-8')


def test_journal_lookup_uses_exact_qualified_name(monkeypatch):
    conn = Connection(None, 'Custom"Schema')
    monkeypatch.setattr(conn, 'execute', Mock())
    conn.execute.return_value.fetchone.return_value = (None,)
    assert not journal_exists(conn)
    conn.execute.assert_called_once_with('SELECT to_regclass(%s)', ('"Custom""Schema"."schema_migrations"',))


def test_import_cli_reports_schema_configuration_error(tmp_path, monkeypatch, capsys):
    from scripts import import_sqlite_to_postgres as importer
    source = tmp_path / 'source.db'
    source.touch()
    monkeypatch.setattr(importer, 'transfer', Mock(side_effect=SchemaConfigurationError("PostgreSQL schema 'planner' does not exist; ask the database administrator to create it")))
    assert importer.main(['--source', str(source)]) == 1
    assert "schema 'planner' does not exist" in capsys.readouterr().err
