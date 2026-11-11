"""Apply migrations independently of the application's selected backend."""
import argparse
import os
import sys

from backend import settings as _settings


def main(argv=None):
    parser = argparse.ArgumentParser(description='Подготовка схемы SQLite или PostgreSQL')
    target = parser.add_mutually_exclusive_group()
    target.add_argument('--database', help='Путь SQLite (по умолчанию database.db)')
    target.add_argument('--postgresql', action='store_true', help='URL из SUPPORT_PLANNER_DATABASE_URL')
    parser.add_argument('--schema-only', action='store_true', help='PostgreSQL без bootstrap для импорта')
    args = parser.parse_args(argv)
    if args.schema_only and not args.postgresql:
        parser.error('--schema-only requires --postgresql')
    conn = None
    try:
        if args.postgresql:
            from backend.db.postgresql import PostgreSQLBackend
            from backend.db.postgresql_migrations import run_migrations
            backend = PostgreSQLBackend(os.environ.get('SUPPORT_PLANNER_DATABASE_URL', ''))
            conn = backend.connect()
            backend.setup_connection(conn)
            run_migrations(conn, backend, schema_only=args.schema_only)
            version = conn.execute('SELECT MAX(version) FROM %s' % conn.qualified_name('schema_migrations')).fetchone()[0]
        else:
            # This CLI flag explicitly selects SQLite, even in a PostgreSQL instance environment.
            os.environ.pop('SUPPORT_PLANNER_DATABASE_URL', None)
            from backend.db.sqlite import SQLiteBackend
            backend = SQLiteBackend(args.database or 'database.db')
            conn = backend.connect()
            backend.setup_connection(conn)
            backend.predeploy_migrate(conn)
            version = conn.execute('PRAGMA user_version').fetchone()[0]
    except Exception as exc:
        print('Database migration failed: %s' % exc, file=sys.stderr)
        return 1
    finally:
        if conn is not None:
            backend.close(conn)
    print('Database migration completed successfully; %s=%s' % ('version' if args.postgresql else 'user_version', version))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
