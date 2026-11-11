"""Independent PostgreSQL migrations: startup validates, only the CLI runs DDL."""
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from backend.db.schema_manifest import TABLES


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    sql: str
    postcondition: Optional[Callable] = None
    render: Optional[Callable] = None

    @property
    def checksum(self):
        return hashlib.sha256(self.sql.encode('utf-8')).hexdigest()


def migrations():
    return (Migration(1, 'sqlite-v15-baseline', Path(__file__).with_name('postgresql_baseline.sql').read_text(encoding='utf-8'), validate_tables, render_baseline),)


def render_baseline(statement, conn):
    """Adapt only the published baseline's object references, not its checksum."""
    def qualify(match):
        table = match.group(2)
        if table not in TABLES:
            raise RuntimeError('Unknown PostgreSQL baseline table: %s' % table)
        return match.group(1) + ' ' + conn.qualified_name(table)
    return re.sub(r'\b(CREATE TABLE|ON|REFERENCES) public\."([a-z_]+)"', qualify, statement)


def validate_manifest(manifest):
    names = set()
    for expected, migration in enumerate(manifest, 1):
        if migration.version != expected or migration.name in names:
            raise RuntimeError('Invalid PostgreSQL migration manifest at version %s' % expected)
        names.add(migration.name)


def journal_exists(conn):
    return conn.execute('SELECT to_regclass(%s)', (conn.qualified_name('schema_migrations'),)).fetchone()[0] is not None


def validate_journal(conn, manifest, require_current=False):
    validate_manifest(manifest)
    if not journal_exists(conn):
        if require_current:
            raise RuntimeError('PostgreSQL schema missing; run scripts.migrate_database --postgresql')
        return 0
    rows = conn.execute('SELECT version, name, checksum FROM %s ORDER BY version' % conn.qualified_name('schema_migrations')).fetchall()
    if len(rows) > len(manifest):
        raise RuntimeError('Unknown newer PostgreSQL schema version')
    for expected, row in zip(manifest, rows):
        if (row[0], row[1], row[2]) != (expected.version, expected.name, expected.checksum):
            raise RuntimeError('PostgreSQL migration journal mismatch at version %s' % expected.version)
    if require_current and len(rows) != len(manifest):
        raise RuntimeError('PostgreSQL schema outdated; run scripts.migrate_database --postgresql')
    return len(rows)


def validate_tables(conn):
    for table, spec in TABLES.items():
        rows = conn.execute('''SELECT column_name, data_type, is_nullable, collation_name, is_identity
                              FROM information_schema.columns
                              WHERE table_schema = %s AND table_name = %s
                              ORDER BY ordinal_position''', (conn.schema, table)).fetchall()
        actual = [(r[0], r[1], r[2] == 'NO') for r in rows]
        if actual != list(spec['columns']):
            raise RuntimeError('PostgreSQL table columns mismatch: %s' % table)
        if any(r[1] == 'text' and r[3] != 'C' for r in rows):
            raise RuntimeError('PostgreSQL text collation mismatch: %s' % table)
        if spec['identity'] and not any(r[0] == 'id' and r[4] == 'YES' for r in rows):
            raise RuntimeError('PostgreSQL identity mismatch: %s' % table)
        primary = conn.execute('''SELECT ARRAY(
            SELECT a.attname FROM unnest(c.conkey) WITH ORDINALITY k(attnum, ordinal)
            JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=k.attnum ORDER BY k.ordinal)
            FROM pg_constraint c WHERE c.conrelid=%s::regclass AND c.contype='p' ''',
                               (conn.qualified_name(table),)).fetchone()
        if not primary or list(primary[0]) != list(spec['key']):
            raise RuntimeError('PostgreSQL primary key mismatch: %s' % table)
        foreign_keys = conn.execute('''SELECT a.attname, parent.relname, pa.attname, c.confdeltype, n.nspname
            FROM pg_constraint c
            JOIN pg_class parent ON parent.oid = c.confrelid
            JOIN pg_namespace n ON n.oid = parent.relnamespace
            JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
            JOIN pg_attribute pa ON pa.attrelid = c.confrelid AND pa.attnum = c.confkey[1]
            WHERE c.conrelid = %s::regclass AND c.contype = 'f' ''', (conn.qualified_name(table),)).fetchall()
        actions = {'a': 'NO ACTION', 'r': 'RESTRICT', 'c': 'CASCADE', 'n': 'SET NULL', 'd': 'SET DEFAULT'}
        actual_fks = sorted((r[0], r[1], r[2], actions[r[3]]) for r in foreign_keys)
        if actual_fks != sorted(spec['foreign_keys']) or any(r[4] != conn.schema for r in foreign_keys):
            raise RuntimeError('PostgreSQL foreign keys mismatch: %s' % table)
        for name, columns, unique, partial in spec['indexes']:
            index = conn.execute('''SELECT i.indisunique, i.indisvalid, i.indisready,
                    pg_get_expr(i.indpred, i.indrelid),
                    ARRAY(SELECT a.attname FROM unnest(i.indkey) WITH ORDINALITY k(attnum, position)
                          JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=k.attnum
                          ORDER BY k.position)
                FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid
                JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname=%s AND c.relname=%s AND i.indrelid=%s::regclass''',
                                 (conn.schema, name, conn.qualified_name(table))).fetchone()
            if (not index or index[0] != unique or not index[1] or not index[2]
                    or bool(index[3]) != partial or list(index[4]) != list(columns)):
                raise RuntimeError('PostgreSQL index mismatch: %s' % name)
            if partial and index[3].replace(' ', '').strip('()') != 'is_deleted=0':
                raise RuntimeError('PostgreSQL partial index predicate mismatch: %s' % name)
        conn.execute('SELECT 1 FROM %s LIMIT 0' % conn.qualified_name(table))
    tables = [conn.qualified_name(name) for name in TABLES]
    bad = conn.execute('''SELECT c.conrelid::regclass::text FROM pg_constraint c
                          JOIN pg_namespace n ON n.oid = c.connamespace
                          WHERE n.nspname = %s AND c.contype = 'f'
                            AND c.conrelid = ANY(%s::regclass[]) AND NOT c.convalidated''', (conn.schema, tables)).fetchone()
    if bad:
        raise RuntimeError('Unvalidated PostgreSQL foreign key: %s' % bad[0])
    disabled = conn.execute('''SELECT tgrelid::regclass::text FROM pg_trigger
                              WHERE tgrelid = ANY(%s::regclass[])
                                AND tgisinternal AND tgenabled NOT IN ('O', 'A')''', (tables,)).fetchone()
    if disabled:
        raise RuntimeError('Disabled PostgreSQL constraint trigger: %s' % disabled[0])


def check_schema(conn):
    version = conn.execute('SHOW server_version_num').fetchone()[0]
    if int(version) < 150000:
        raise RuntimeError('PostgreSQL 15 or newer is required')
    validate_journal(conn, migrations(), require_current=True)
    validate_tables(conn)


def run_migrations(conn, backend, manifest=None, schema_only=False):
    manifest = migrations() if manifest is None else tuple(manifest)
    validate_manifest(manifest)
    with backend.migration_lock(conn):
        fresh = not journal_exists(conn)
        applied = validate_journal(conn, manifest)
        conn.rollback()
        for migration in manifest[applied:]:
            try:
                backend.begin_write(conn)
                conn.execute('''CREATE TABLE IF NOT EXISTS %s (
                    version BIGINT PRIMARY KEY,
                    name TEXT COLLATE "C" NOT NULL UNIQUE,
                    checksum TEXT COLLATE "C" NOT NULL,
                    applied_at TEXT COLLATE "C" NOT NULL DEFAULT
                        to_char(clock_timestamp() AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS')
                )''' % conn.qualified_name('schema_migrations'))
                conn.execute(migration.render(migration.sql, conn) if migration.render else migration.sql)
                if migration.postcondition:
                    migration.postcondition(conn)
                conn.execute('INSERT INTO {} (version, name, checksum) VALUES (%s, %s, %s)'.format(conn.qualified_name('schema_migrations', parameters=True)),
                             (migration.version, migration.name, migration.checksum))
                if fresh and not schema_only and migration.version == len(manifest):
                    bootstrap(conn)
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
        validate_journal(conn, manifest, require_current=True)
        conn.rollback()


def bootstrap(conn):
    from backend.auth import hash_password
    if any(conn.execute('SELECT 1 FROM %s LIMIT 1' % conn.qualified_name(table)).fetchone() for table in TABLES):
        raise RuntimeError('Bootstrap requires a new empty PostgreSQL installation')
    conn.execute('''INSERT INTO {} (last_name, first_name, role, login, password_hash, is_assignee)
                    VALUES (%s, %s, 'admin', 'admin', %s, 0)'''.format(conn.qualified_name('users', parameters=True)),
                 (None, 'Администратор', hash_password('q12345678')))
