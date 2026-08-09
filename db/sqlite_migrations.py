from dataclasses import dataclass
from typing import Callable, Iterable


MigrationOperation = Callable[[object], None]


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    operation: MigrationOperation


def current_version(conn) -> int:
    return int(conn.execute('PRAGMA user_version').fetchone()[0])


def run_migrations(conn, migrations: Iterable[Migration]) -> None:
    """Apply ordered migrations once and persist each completed version."""
    applied_version = current_version(conn)
    expected_version = applied_version + 1
    for migration in migrations:
        if migration.version <= applied_version:
            continue
        if migration.version != expected_version:
            raise RuntimeError(
                f'Migration registry gap: expected version {expected_version}, got {migration.version}'
            )
        migration.operation(conn)
        conn.execute(f'PRAGMA user_version = {migration.version}')
        conn.commit()
        applied_version = migration.version
        expected_version += 1
