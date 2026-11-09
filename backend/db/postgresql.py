"""Psycopg boundary: native SQL parameters, compatible rows and safe diagnostics."""

from contextlib import contextmanager
from urllib.parse import urlsplit
from uuid import uuid4

from backend.db.backend import DBBackend

WRITE_LOCK = 734918527101
MIGRATION_LOCK = 734918527102


class StorageError(Exception):
    pass


class StorageIntegrityError(StorageError):
    pass


class UniqueConstraintError(StorageIntegrityError):
    pass


class ForeignKeyConstraintError(StorageIntegrityError):
    pass


def driver_error(exc):
    code = getattr(exc, 'sqlstate', None)
    kind = {'23505': UniqueConstraintError, '23503': ForeignKeyConstraintError}.get(code)
    if kind is None:
        kind = StorageIntegrityError if code and code.startswith('23') else StorageError
    return kind('PostgreSQL operation failed (SQLSTATE: %s)' % (code or 'unavailable'))


class Row:
    def __init__(self, names, values):
        self._names = names
        self._values = tuple(values)

    def __getitem__(self, key):
        if isinstance(key, (int, slice)):
            return self._values[key]
        try:
            return self._values[self._names.index(key)]
        except ValueError:
            raise KeyError(key) from None

    def __iter__(self):
        return iter(self._values)

    def keys(self):
        return self._names

    def __len__(self):
        return len(self._names)


def row_factory(cursor):
    names = tuple(column.name for column in cursor.description) if cursor.description else ()
    return lambda values: Row(names, values)


class Cursor:
    def __init__(self, cursor):
        self.raw = cursor

    def execute(self, statement, params=None):
        import psycopg
        try:
            self.raw.execute(statement, params)
            return self
        except psycopg.Error as exc:
            raise driver_error(exc) from None

    def executemany(self, statement, params):
        import psycopg
        try:
            self.raw.executemany(statement, params)
            return self
        except psycopg.Error as exc:
            raise driver_error(exc) from None

    def __getattr__(self, name):
        return getattr(self.raw, name)

    def __iter__(self):
        while True:
            row = self.fetchone()
            if row is None:
                return
            yield row

    def _fetch(self, method, *args):
        import psycopg
        try:
            return getattr(self.raw, method)(*args)
        except psycopg.Error as exc:
            raise driver_error(exc) from None

    def fetchone(self):
        return self._fetch('fetchone')

    def fetchmany(self, size=1000):
        return self._fetch('fetchmany', size)

    def fetchall(self):
        return self._fetch('fetchall')

    def close(self):
        return self._fetch('close')


class Connection:
    def __init__(self, raw):
        self.raw = raw
        self.write_locked = False

    def cursor(self, name=None):
        return Cursor(self.raw.cursor(name=name) if name else self.raw.cursor())

    def execute(self, statement, params=None):
        return self.cursor().execute(statement, params)

    def executemany(self, statement, params):
        return self.cursor().executemany(statement, params)

    def commit(self):
        import psycopg
        try:
            self.raw.commit()
        except psycopg.Error as exc:
            raise driver_error(exc) from None
        finally:
            self.write_locked = False

    def rollback(self):
        import psycopg
        try:
            self.raw.rollback()
        except psycopg.Error as exc:
            raise driver_error(exc) from None
        finally:
            self.write_locked = False

    def close(self):
        import psycopg
        try:
            self.raw.close()
        except psycopg.Error as exc:
            raise driver_error(exc) from None


def validate_url(url):
    try:
        parts = urlsplit(url)
        valid = parts.scheme in ('postgres', 'postgresql') and bool(parts.hostname or parts.path)
        parts.port
    except (ValueError, TypeError):
        valid = False
    if not valid or not url or any(char in url for char in ('\n', '\r', '\x00')):
        raise StorageError('Invalid SUPPORT_PLANNER_DATABASE_URL: expected a PostgreSQL URI') from None
    return url


def database_identity(conn):
    """Identify a configured test destination without including credentials."""
    row = conn.execute('SELECT current_database(), inet_server_addr()::text, inet_server_port()').fetchone()
    return row[0], row[1] or conn.raw.info.host, row[2] or conn.raw.info.port


class PostgreSQLBackend(DBBackend):
    name = 'postgresql'
    placeholder = '%s'
    now_sql = "to_char(clock_timestamp() AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS')"
    db_error = StorageError
    duplicate_error = UniqueConstraintError
    integrity_error = StorageIntegrityError

    def __init__(self, url):
        self.url = validate_url(url)

    def connect(self):
        import psycopg
        try:
            raw = psycopg.connect(self.url, row_factory=row_factory, connect_timeout=10)
            raw.isolation_level = psycopg.IsolationLevel.READ_COMMITTED
            return Connection(raw)
        except (psycopg.Error, ValueError) as exc:
            raise driver_error(exc) from None

    def setup_connection(self, conn):
        conn.execute("SET search_path TO public")
        conn.execute("SET TIME ZONE 'UTC'")
        conn.commit()

    def close(self, conn):
        from psycopg.pq import TransactionStatus
        try:
            if not conn.raw.closed and conn.raw.info.transaction_status != TransactionStatus.IDLE:
                conn.rollback()
        finally:
            conn.close()

    def begin_write(self, conn):
        if not conn.write_locked:
            conn.execute('SELECT pg_advisory_xact_lock(%s)', (WRITE_LOCK,))
            conn.write_locked = True

    def insert_id(self, conn, statement, params=()):
        return conn.execute(statement + ' RETURNING id', params).fetchone()[0]

    def candidate_cursor(self, conn, query, params):
        cursor = conn.cursor(name='sp_candidates_' + uuid4().hex)
        try:
            return cursor.execute(query, params)
        except BaseException:
            cursor.close()
            raise

    def last_insert_id(self, cursor):
        return cursor.fetchone()[0]

    def is_unique(self, exc):
        return isinstance(exc, UniqueConstraintError)

    def is_foreign_key(self, exc):
        return isinstance(exc, ForeignKeyConstraintError)

    def init_schema(self, conn):
        from backend.db.postgresql_migrations import check_schema
        check_schema(conn)

    @contextmanager
    def migration_lock(self, conn):
        conn.execute('SELECT pg_advisory_lock(%s)', (MIGRATION_LOCK,))
        conn.commit()
        try:
            yield
        finally:
            conn.rollback()
            conn.execute('SELECT pg_advisory_unlock(%s)', (MIGRATION_LOCK,))
            conn.commit()
