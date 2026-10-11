import hashlib
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

MigrationOperation = Callable[[object], None]
MigrationValidator = Callable[[object], None]
MIGRATION_LOG_TABLE = 'schema_migrations'


def manifest_checksum(version: int, name: str, revision: str = '1') -> str:
    value = f'{version}:{name}:{revision}'.encode('utf-8')
    return hashlib.sha256(value).hexdigest()


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    operation: MigrationOperation
    checksum: str = ''
    postcondition: Optional[MigrationValidator] = None
    foreign_keys_disabled: bool = False

    @property
    def effective_checksum(self) -> str:
        return self.checksum or manifest_checksum(self.version, self.name)


def current_version(conn) -> int:
    return int(conn.execute('PRAGMA user_version').fetchone()[0])


def _table_exists(conn, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone() is not None


def _validate_registry(migrations: tuple[Migration, ...]) -> None:
    seen_names = set()
    for expected, migration in enumerate(migrations, start=1):
        if migration.version != expected:
            raise RuntimeError(
                f'Migration registry gap: expected version {expected}, got {migration.version}'
            )
        if migration.name in seen_names:
            raise RuntimeError(f'Duplicate migration name: {migration.name}')
        if not migration.effective_checksum:
            raise RuntimeError(f'Migration {migration.version} has no checksum')
        seen_names.add(migration.name)


def _create_migration_log(conn) -> None:
    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS {MIGRATION_LOG_TABLE} (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            checksum TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')


def _bootstrap_migration_log(conn, migrations: tuple[Migration, ...], applied_version: int) -> None:
    count = conn.execute(f'SELECT COUNT(*) FROM {MIGRATION_LOG_TABLE}').fetchone()[0]
    if count:
        return
    conn.executemany(
        f'INSERT INTO {MIGRATION_LOG_TABLE} (version, name, checksum) VALUES (?, ?, ?)',
        [(item.version, item.name, item.effective_checksum) for item in migrations[:applied_version]],
    )


def _validate_migration_log(conn, migrations: tuple[Migration, ...], applied_version: int) -> None:
    if not _table_exists(conn, MIGRATION_LOG_TABLE):
        if applied_version == len(migrations):
            raise RuntimeError(
                f'Migration journal {MIGRATION_LOG_TABLE} is missing at user_version {applied_version}'
            )
        return
    rows = conn.execute(
        f'SELECT version, name, checksum FROM {MIGRATION_LOG_TABLE} ORDER BY version'
    ).fetchall()
    if len(rows) != applied_version:
        raise RuntimeError(
            f'Migration journal mismatch: user_version is {applied_version}, journal has {len(rows)} rows'
        )
    for index, row in enumerate(rows):
        expected = migrations[index]
        actual = (row[0], row[1], row[2])
        wanted = (expected.version, expected.name, expected.effective_checksum)
        if actual != wanted:
            raise RuntimeError(
                f'Migration journal mismatch at version {expected.version}: '
                f'expected {wanted[1]}/{wanted[2]}, got {actual[1]}/{actual[2]}'
            )


def _validate_foreign_keys(conn, migration_version: int) -> None:
    violations = conn.execute('PRAGMA foreign_key_check').fetchall()
    if violations:
        first = violations[0]
        raise RuntimeError(
            f'Migration {migration_version} foreign key check failed: '
            f'table={first[0]}, rowid={first[1]}, parent={first[2]}'
        )


def run_migrations(
        conn,
        migrations: Iterable[Migration],
) -> None:
    """Apply ordered migrations atomically and validate the resulting database."""
    registry = tuple(migrations)
    _validate_registry(registry)
    applied_version = current_version(conn)
    latest_version = len(registry)
    if applied_version > latest_version:
        raise RuntimeError(
            f'Database user_version {applied_version} is newer than supported version {latest_version}'
        )
    _validate_migration_log(conn, registry, applied_version)

    for migration in registry[applied_version:]:
        foreign_keys_were_enabled = bool(conn.execute('PRAGMA foreign_keys').fetchone()[0])
        if migration.foreign_keys_disabled and foreign_keys_were_enabled:
            conn.execute('PRAGMA foreign_keys = OFF')
        try:
            conn.execute('BEGIN IMMEDIATE')
            _create_migration_log(conn)
            _bootstrap_migration_log(conn, registry, applied_version)
            migration.operation(conn)
            if migration.postcondition is not None:
                migration.postcondition(conn)
            _validate_foreign_keys(conn, migration.version)
            conn.execute(
                f'INSERT INTO {MIGRATION_LOG_TABLE} (version, name, checksum) VALUES (?, ?, ?)',
                (migration.version, migration.name, migration.effective_checksum),
            )
            conn.execute(f'PRAGMA user_version = {migration.version}')
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            if migration.foreign_keys_disabled and foreign_keys_were_enabled:
                conn.execute('PRAGMA foreign_keys = ON')
        applied_version = migration.version

    _validate_migration_log(conn, registry, applied_version)


def run_quick_check(conn) -> None:
    rows = [tuple(row) for row in conn.execute('PRAGMA quick_check').fetchall()]
    if rows != [('ok',)]:
        details = '; '.join(str(row[0]) for row in rows)
        raise RuntimeError(f'SQLite quick_check failed: {details}')
