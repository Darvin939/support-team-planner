"""Production UI context: fresh build, safe backup/restore and owned-process cleanup."""
import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = 'http://127.0.0.1:5093'


def stop_process(process):
    if process is not None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def sqlite_digest(conn):
    import hashlib
    return hashlib.sha256('\n'.join(conn.iterdump()).encode('utf-8')).hexdigest()


def sqlite_backup(source, target):
    src = sqlite3.connect(str(source))
    dst = sqlite3.connect(str(target))
    try:
        src.backup(dst)
        dst.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        if dst.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise RuntimeError('SQLite backup/restore integrity failure')
        if sqlite_digest(src) != sqlite_digest(dst):
            raise RuntimeError('SQLite restored contents differ')
    finally:
        dst.close()
        src.close()


def pg_tool(command, url):
    from psycopg.conninfo import conninfo_to_dict
    from psycopg.pq import Conninfo
    env = os.environ.copy()
    # Use libpq's own option/environment mapping; no DSN or password in command arguments.
    options = conninfo_to_dict(url)
    for option in Conninfo.get_defaults():
        keyword = option.keyword.decode()
        if keyword in options and option.envvar:
            env[option.envvar.decode()] = options[keyword]
    if command[0] == 'pg_restore':
        command = command[:-1] + ['--dbname', options.get('dbname', options.get('user', 'postgres')), command[-1]]
    result = subprocess.run(command, env=env, capture_output=True)
    if result.returncode:
        raise RuntimeError('%s failed; inspect the isolated test database configuration' % command[0])


def pg_digest(url, schema=None):
    from backend.db.postgresql import PostgreSQLBackend
    from backend.db.schema_manifest import TABLES
    from scripts.import_sqlite_to_postgres import table_digest
    backend = PostgreSQLBackend(url, schema=schema)
    conn = backend.connect()
    try:
        backend.setup_connection(conn)
        return {table: table_digest(conn, table, spec, postgres=True) for table, spec in TABLES.items()}
    finally:
        backend.close(conn)


@contextmanager
def production_backend():
    from backend import settings as _settings
    env = os.environ.copy()
    env.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    env['SUPPORT_PLANNER_SKIP_DOTENV'] = '1'
    mode = env.get('SUPPORT_PLANNER_TEST_BACKEND', 'sqlite')
    output = ROOT / '.tmp' / ('storage-ui-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:8])
    output.mkdir(parents=True)
    temporary = tempfile.TemporaryDirectory(prefix='support-ui-')
    backend = None
    backup = None
    original = None
    log = None
    restore_needed = False
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1', 5093)) == 0:
            raise RuntimeError('Port 5093 is occupied; the existing process was left untouched')
    try:
        if mode == 'postgresql':
            url = env.get('SUPPORT_PLANNER_TEST_DATABASE_URL')
            if not url:
                raise RuntimeError('PostgreSQL UI requires SUPPORT_PLANNER_TEST_DATABASE_URL')
            env['SUPPORT_PLANNER_DATABASE_URL'] = url
            tool_url = env.get('SUPPORT_PLANNER_TEST_MIGRATION_URL', url)
            schema = env.get('SUPPORT_PLANNER_DATABASE_SCHEMA', 'planner')
            env['SUPPORT_PLANNER_DATABASE_SCHEMA'] = schema
            from backend.db.postgresql import PostgreSQLBackend, database_identity
            identities = []
            for selected_url in (url, tool_url):
                selected = PostgreSQLBackend(selected_url, schema=schema)
                connection = selected.connect()
                try:
                    selected.setup_connection(connection)
                    identities.append(database_identity(connection))
                finally:
                    selected.close(connection)
            if identities[0] != identities[1]:
                raise RuntimeError('UI runtime and migration URLs identify different databases; no restore will run')
            backup = output / 'before.dump'
            original = pg_digest(url, schema)
            pg_tool(['pg_dump', '--format=custom', '--file', str(backup)], tool_url)
        elif mode == 'sqlite':
            env.pop('SUPPORT_PLANNER_DATABASE_URL', None)
            # Existing local data is backed up; a fresh checkout uses an isolated empty file.
            path = Path(env.get('SUPPORT_PLANNER_DB_PATH', str(ROOT / 'database.db'))).resolve()
            if not path.exists():
                path = Path(temporary.name) / 'database.db'
            env['SUPPORT_PLANNER_DB_PATH'] = str(path)
            backup = output / 'database.db.ui-test.bak'
            with backup.open('xb'):
                pass
            sqlite_backup(path, backup)
        else:
            raise RuntimeError('Unknown UI test backend')
        with (output / 'build.log').open('w', encoding='utf-8') as build_log:
            command = ['cmd.exe', '/c', 'npm.cmd', 'run', 'build'] if os.name == 'nt' else ['npm', 'run', 'build']
            subprocess.run(command, cwd=ROOT / 'frontend', env=env, stdout=build_log, stderr=subprocess.STDOUT, check=True)
        log = (output / 'backend.log').open('w', encoding='utf-8')
        restore_needed = True
        backend = subprocess.Popen([sys.executable, 'support_planner.py'], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        for _ in range(80):
            if backend.poll() is not None:
                raise RuntimeError('Backend stopped before startup; see %s' % (output / 'backend.log'))
            try:
                with urllib.request.urlopen(BASE_URL + '/login', timeout=1) as response:
                    if response.status == 200:
                        break
            except Exception:
                time.sleep(0.25)
        else:
            raise RuntimeError('Backend did not become ready on 5093')
        yield BASE_URL, output
    finally:
        stop_process(backend)
        if log is not None:
            log.close()
        try:
            if restore_needed:
                if mode == 'postgresql':
                    pg_tool(['pg_restore', '--clean', '--if-exists', '--exit-on-error', '--no-owner', str(backup)], tool_url)
                    if pg_digest(env['SUPPORT_PLANNER_TEST_DATABASE_URL'], schema) != original:
                        raise RuntimeError('PostgreSQL restored data differs from backup')
                else:
                    sqlite_backup(backup, path)
        finally:
            temporary.cleanup()
