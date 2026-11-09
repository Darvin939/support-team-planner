import contextvars
import os
from contextlib import contextmanager
from functools import wraps
from inspect import signature

from backend.db.backend import DBBackend
from backend.db.sqlite import SQLiteBackend
from backend.db.errors import IntegrityConstraintError

# Backend selection stays at the infrastructure boundary. Domain DAO modules only use the
# generic operations exposed by DBBackend and do not depend on sqlite connection/cursor types.
def select_backend():
    if 'SUPPORT_PLANNER_DATABASE_URL' in os.environ:
        from backend.db.postgresql import PostgreSQLBackend
        return PostgreSQLBackend(os.environ['SUPPORT_PLANNER_DATABASE_URL'])
    return SQLiteBackend()


backend: DBBackend = select_backend()

_request_conn: contextvars.ContextVar = contextvars.ContextVar('request_conn', default=None)
_composite_transaction_active: contextvars.ContextVar = contextvars.ContextVar(
    'composite_transaction_active', default=False
)


def set_request_connection(conn):
    """Bind a connection to the current request context and return its reset token."""
    return _request_conn.set(conn)


def clear_request_connection(token):
    """Remove the connection bound to the current request context."""
    _request_conn.reset(token)


def get_db_connection():
    conn = backend.connect()
    try:
        backend.setup_connection(conn)
    except BaseException:
        conn.close()
        raise
    return conn


@contextmanager
def composite_transaction():
    """Run multiple decorated DAO calls as one explicit transaction."""
    if _composite_transaction_active.get():
        raise RuntimeError('Nested composite transactions are not supported')

    shared_conn = _request_conn.get()
    conn = shared_conn if shared_conn is not None else get_db_connection()
    connection_token = None
    if shared_conn is None:
        connection_token = _request_conn.set(conn)
    state = {'failed': False}
    transaction_token = _composite_transaction_active.set(state)
    try:
        backend.begin_write(conn)
        yield
        if state['failed']:
            raise RuntimeError('Composite transaction contains a failed DAO operation')
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        _composite_transaction_active.reset(transaction_token)
        if connection_token is not None:
            _request_conn.reset(connection_token)
            conn.close()


def with_db_connection(default_return=None, raise_on_error=True, commit_on_success=True, write=False):
    """Inject the current request connection or create a short-lived connection."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            shared_conn = _request_conn.get()
            conn = shared_conn if shared_conn is not None else get_db_connection()
            try:
                if write:
                    backend.begin_write(conn)
                result = func(conn, *args, **kwargs)
                if commit_on_success and not _composite_transaction_active.get():
                    conn.commit()
                return result
            except BaseException as exc:
                state = _composite_transaction_active.get()
                if state:
                    state['failed'] = True
                else:
                    conn.rollback()
                if raise_on_error and isinstance(exc, backend.integrity_error) and backend.is_foreign_key(exc):
                    raise IntegrityConstraintError('Нарушена связь: связанная запись отсутствует или используется другими данными') from None
                if raise_on_error or not isinstance(exc, backend.db_error):
                    raise
                return default_return
            finally:
                if shared_conn is None:
                    backend.close(conn)

        # The connection parameter is an implementation detail injected by this boundary.
        # Public DAO signatures expose only domain arguments.
        function_signature = signature(func)
        wrapper.__signature__ = function_signature.replace(
            parameters=list(function_signature.parameters.values())[1:]
        )
        return wrapper

    return decorator


def init_db():
    conn = get_db_connection()
    try:
        backend.init_schema(conn)
    finally:
        backend.close(conn)
