"""Full verified SQLite -> PostgreSQL transfer; replacement is explicit and atomic."""
import argparse
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import time
from uuid import uuid4
from datetime import datetime, timezone
from pathlib import Path

from backend import settings as _settings


class TransferError(Exception):
    pass


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def unique_file(source, suffix):
    handle, name = tempfile.mkstemp(prefix=source.name + '.transfer-', suffix=suffix, dir=str(source.parent))
    os.close(handle)
    return Path(name)


def backup_sqlite(source, target):
    original = sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True)
    try:
        copy = sqlite3.connect(str(target))
        try:
            original.backup(copy)
        finally:
            copy.close()
    finally:
        original.close()


def prepare_source(source, report):
    from backend.db.sqlite import SQLiteBackend, sqlite_migrations
    from backend.db.sqlite_migrations import run_migrations, run_quick_check
    if not source.is_file():
        raise TransferError('SQLite source file does not exist')
    snapshot = unique_file(source, '.bak')
    report['snapshot'] = {'path': str(snapshot), 'started_at': utc_now()}
    backup_sqlite(source, snapshot)
    report['snapshot']['completed_at'] = utc_now()
    working = unique_file(source, '.sqlite')
    report['working_copy'] = str(working)
    backup_sqlite(snapshot, working)
    backend = SQLiteBackend(str(working))
    conn = backend.connect()
    try:
        backend.setup_connection(conn)
        run_quick_check(conn)
        run_migrations(conn, sqlite_migrations(bootstrap=False))
        run_quick_check(conn)
        if conn.execute('PRAGMA foreign_key_check').fetchone():
            raise TransferError('SQLite foreign key check failed')
        validate_source(conn)
        report['source_version'] = conn.execute('PRAGMA user_version').fetchone()[0]
        return conn
    except BaseException:
        conn.close()
        raise


def validate_source(conn):
    from backend.db.schema_manifest import TABLES
    for table, spec in TABLES.items():
        actual = {row[1] for row in conn.execute('PRAGMA table_info("%s")' % table)}
        expected = {column[0] for column in spec['columns']}
        if actual != expected:
            raise TransferError('SQLite columns mismatch: %s' % table)
        # Validate the model even if a damaged/legacy source lost an index or FK.
        # PRAGMA foreign_key_check alone only checks constraints that still exist.
        for column, parent, parent_column, _action in spec['foreign_keys']:
            orphan = conn.execute('''SELECT 1 FROM "%s" child
                LEFT JOIN "%s" parent ON child."%s" = parent."%s"
                WHERE child."%s" IS NOT NULL AND parent."%s" IS NULL LIMIT 1''' %
                (table, parent, column, parent_column, column, parent_column)).fetchone()
            if orphan:
                raise TransferError('SQLite foreign key check failed: table=%s column=%s' % (table, column))
        unique_keys = [(spec['key'], False)] + [
            (columns, partial) for _name, columns, unique, partial in spec['indexes'] if unique
        ]
        for key_columns, partial in unique_keys:
            key_sql = ','.join('"%s"' % column for column in key_columns)
            where = ' AND '.join('"%s" IS NOT NULL' % column for column in key_columns)
            if partial:
                where += ' AND is_deleted = 0'
            duplicate = conn.execute('''SELECT 1 FROM "%s" WHERE %s
                GROUP BY %s HAVING COUNT(*) > 1 LIMIT 1''' % (table, where, key_sql)).fetchone()
            if duplicate:
                raise TransferError('SQLite unique key check failed: table=%s columns=%s' % (table, ','.join(key_columns)))
        if table == 'application_metadata' and conn.execute('SELECT 1 FROM application_metadata WHERE id != 1 LIMIT 1').fetchone():
            raise TransferError('SQLite application_metadata singleton check failed')
        columns = ','.join('"%s"' % column[0] for column in spec['columns'])
        for row in conn.execute('SELECT %s FROM "%s"' % (columns, table)):
            for (name, kind, required), value in zip(spec['columns'], row):
                valid = value is not None or not required
                if value is not None:
                    if kind == 'text':
                        valid = isinstance(value, str) and '\x00' not in value
                        if valid:
                            try:
                                value.encode('utf-8', errors='strict')
                            except UnicodeError:
                                valid = False
                    else:
                        bound = 2 ** (63 if kind == 'bigint' else 31)
                        valid = type(value) is int and -bound <= value < bound
                if not valid:
                    keys = {key: row[[c[0] for c in spec['columns']].index(key)] for key in spec['key']}
                    raise TransferError('Unrepresentable value: table=%s key=%s column=%s' % (table, json.dumps(keys, ensure_ascii=True), name))
        if spec['identity']:
            maximum = conn.execute('SELECT MAX(id) FROM "%s"' % table).fetchone()[0]
            if maximum is not None and maximum >= 2 ** 63 - 1:
                raise TransferError('Identity exhausted: table=%s' % table)


def table_digest(conn, table, spec, postgres=False):
    columns = ','.join('"%s"' % item[0] for item in spec['columns'])
    keys = ','.join('"%s"' % item for item in spec['key'])
    relation = conn.qualified_name(table) if postgres else '"%s"' % table
    query = 'SELECT %s FROM %s ORDER BY %s' % (columns, relation, keys)
    if postgres:
        cursor = conn.cursor(name='sp_verify_' + uuid4().hex).execute(query)
    else:
        cursor = conn.execute(query)
    content_hash, key_hash = hashlib.sha256(), hashlib.sha256()
    key_indices = [[item[0] for item in spec['columns']].index(key) for key in spec['key']]
    count = 0
    try:
        while True:
            rows = cursor.fetchmany(1000)
            if not rows:
                break
            for row in rows:
                values = [row[index] for index in range(len(spec['columns']))]
                encoded = json.dumps(values, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
                content_hash.update(encoded + b'\n')
                key_hash.update(json.dumps([values[index] for index in key_indices], ensure_ascii=False, separators=(',', ':')).encode('utf-8') + b'\n')
                count += 1
    finally:
        cursor.close()
    return {'count': count, 'keys_sha256': key_hash.hexdigest(), 'content_sha256': content_hash.hexdigest()}


def target_counts(conn, allow_missing=False):
    from backend.db.schema_manifest import TABLES
    counts = {}
    for table in TABLES:
        exists = conn.execute('SELECT to_regclass(%s)', (conn.qualified_name(table),)).fetchone()[0]
        if not exists:
            if not allow_missing:
                raise TransferError('Missing PostgreSQL table: %s' % table)
            counts[table] = 0
        else:
            counts[table] = conn.execute('SELECT COUNT(*) FROM %s' % conn.qualified_name(table)).fetchone()[0]
    return counts


def validate_target_scope(conn):
    """Refuse inherited tables, user triggers and incoming FKs outside the manifest."""
    from backend.db.schema_manifest import TABLES
    names = [conn.qualified_name(table) for table in TABLES]
    external = conn.execute('''SELECT 1 FROM pg_constraint
        WHERE contype = 'f' AND confrelid = ANY(%s::regclass[])
          AND NOT (conrelid = ANY(%s::regclass[])) LIMIT 1''', (names, names)).fetchone()
    inherited = conn.execute('''SELECT 1 FROM pg_inherits
        WHERE inhparent = ANY(%s::regclass[]) OR inhrelid = ANY(%s::regclass[]) LIMIT 1''', (names, names)).fetchone()
    triggers = conn.execute('''SELECT 1 FROM pg_trigger
        WHERE tgrelid = ANY(%s::regclass[]) AND NOT tgisinternal AND tgenabled != 'D' LIMIT 1''', (names,)).fetchone()
    if external or inherited or triggers:
        raise TransferError('Target has external dependencies, inheritance or application triggers; replacement scope is unsafe')


def load_table(source, target, backend, table, spec):
    columns = ','.join('"%s"' % item[0] for item in spec['columns'])
    query = 'INSERT INTO %s (%s) VALUES (%s)' % (target.qualified_name(table, parameters=True), columns, backend.placeholders(len(spec['columns'])))
    cursor = source.execute('SELECT %s FROM "%s" ORDER BY %s' % (columns, table, ','.join('"%s"' % key for key in spec['key'])))
    try:
        while True:
            rows = cursor.fetchmany(1000)
            if not rows:
                break
            # Each failure identifies only the table/key, never a password hash or full row.
            for row in rows:
                try:
                    target.execute(query, tuple(row))
                except Exception:
                    key = {key: row[key] for key in spec['key']}
                    raise TransferError('Import failed: table=%s key=%s' % (table, json.dumps(key, ensure_ascii=True))) from None
    finally:
        cursor.close()


def verify_tables(source, target):
    from backend.db.schema_manifest import TABLES
    results = {}
    for table, spec in TABLES.items():
        expected = table_digest(source, table, spec)
        actual = table_digest(target, table, spec, postgres=True)
        if expected != actual:
            raise TransferError('Verification mismatch: table=%s' % table)
        results[table] = actual
    return results


def restart_sequences(conn):
    from psycopg import sql
    from backend.db.schema_manifest import TABLES
    for table, spec in TABLES.items():
        if not spec['identity']:
            continue
        row = conn.execute('''SELECT n.nspname, c.relname FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.oid = pg_get_serial_sequence(%s, 'id')::regclass''', (conn.qualified_name(table),)).fetchone()
        if not row:
            raise TransferError('Missing identity sequence: %s' % table)
        maximum = conn.execute('SELECT MAX(id) FROM %s' % conn.qualified_name(table)).fetchone()[0]
        next_id = max(1, (maximum or 0) + 1)
        conn.execute(sql.SQL('ALTER SEQUENCE {} RESTART WITH {}').format(sql.Identifier(row[0], row[1]), sql.Literal(next_id)))


def transfer(source_path, replace=False, dry_run=False, report=None):
    from backend.db.postgresql import PostgreSQLBackend
    from backend.db.postgresql_migrations import check_schema, journal_exists, run_migrations
    from backend.db.schema_manifest import TABLES
    result = report if report is not None else {}
    result.update({'mode': 'replace' if replace else 'import', 'dry_run': dry_run, 'started_at': utc_now(), 'commit': 'not_started'})
    started = time.monotonic()
    source = target = None
    try:
        source = prepare_source(Path(source_path).resolve(), result)
        backend = PostgreSQLBackend(os.environ.get('SUPPORT_PLANNER_DATABASE_URL', ''))
        target = backend.connect()
        backend.setup_connection(target)
        target.execute("SET lock_timeout TO '10s'")
        target.commit()
        row = target.execute('SELECT current_database(), current_schema(), current_user, version()').fetchone()
        result['target'] = {'database': row[0], 'schema': row[1], 'role': row[2], 'server': row[3]}
        target.rollback()
        exists = journal_exists(target)
        if exists or replace:
            check_schema(target)
        elif target.execute('SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=%s AND table_name = ANY(%s)', (target.schema, list(TABLES))).fetchone()[0]:
            raise TransferError('Target has application tables without a compatible migration journal')
        before = target_counts(target, allow_missing=not exists and not replace)
        result['before_counts'] = before
        if not replace and any(before.values()):
            raise TransferError('Target is not empty; use --replace-target only for an approved full replacement')
        if replace:
            validate_target_scope(target)
            result['replacement_tables'] = list(TABLES)
        target.rollback()
        if dry_run:
            result['commit'] = 'dry_run'
            return result
        if not exists and not replace:
            run_migrations(target, backend, schema_only=True)
        with backend.migration_lock(target):
            backend.begin_write(target)
            table_list = ', '.join('ONLY %s' % target.qualified_name(table) for table in TABLES)
            target.execute('LOCK TABLE %s IN ACCESS EXCLUSIVE MODE' % table_list)
            check_schema(target)
            before = target_counts(target)
            result['before_counts'] = before
            if not replace and any(before.values()):
                raise TransferError('Target is no longer empty')
            if replace:
                validate_target_scope(target)
                target.execute('TRUNCATE TABLE %s RESTART IDENTITY RESTRICT' % table_list)
            result['commit'] = 'in_progress'
            for table, spec in TABLES.items():
                load_table(source, target, backend, table, spec)
            result['verification'] = verify_tables(source, target)
            restart_sequences(target)
            result['commit'] = 'unknown'
            target.commit()
            result['commit'] = 'committed'
        return result
    except BaseException:
        if result['commit'] not in ('unknown', 'committed'):
            result['commit'] = 'rolled_back'
        raise
    finally:
        result['duration_seconds'] = round(time.monotonic() - started, 3)
        result['finished_at'] = utc_now()
        if source is not None:
            source.close()
        if target is not None:
            try:
                backend.close(target)
            except Exception:
                pass


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--replace-target', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args(argv)
    if not args.source.is_file():
        parser.error('SQLite source file does not exist')
    report_path = args.report or unique_file(args.source.resolve(), '.report.json')
    if args.report:
        # Reserve rather than overwrite an operator's previous report.
        try:
            with report_path.open('x', encoding='utf-8'):
                pass
        except FileExistsError:
            parser.error('Report already exists')
    report = {}
    code = 0
    try:
        transfer(args.source, args.replace_target, args.dry_run, report)
    except Exception as exc:
        from backend.db.postgresql import SchemaConfigurationError
        report['error'] = str(exc) if isinstance(exc, (TransferError, SchemaConfigurationError)) else 'Transfer failed (%s); inspect source integrity and target configuration' % type(exc).__name__
        if report.get('commit') == 'unknown':
            report['error'] = 'Commit outcome unknown: inspect PostgreSQL before any retry. No automatic retry was attempted.'
        code = 1
    finally:
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Transfer %s; report: %s' % (report.get('commit', 'failed'), report_path))
    if code:
        print(report['error'], file=sys.stderr)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
