"""Apply and validate SQLite migrations before starting the application."""

import argparse
import os
import sys


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Apply and validate support planner SQLite migrations')
    parser.add_argument('--database', default='database.db', help='Path to the SQLite database file')
    args = parser.parse_args(argv)
    os.environ['SUPPORT_PLANNER_DB_PATH'] = args.database

    try:
        from db.sqlite import SQLiteBackend

        backend = SQLiteBackend()
        conn = backend.connect()
        try:
            backend.setup_connection(conn)
            backend.predeploy_migrate(conn)
            version = conn.execute('PRAGMA user_version').fetchone()[0]
        finally:
            conn.close()
    except Exception as exc:
        print(f'Database migration failed: {exc}', file=sys.stderr)
        return 1

    print(f'Database migration completed successfully; user_version={version}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
