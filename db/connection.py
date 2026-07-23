import contextvars
from contextlib import contextmanager
from functools import wraps
from inspect import signature

from db.backend import DBBackend
from db.sqlite import SQLiteBackend


# Backend selection stays at the infrastructure boundary. Domain DAO modules only use the
# generic operations exposed by DBBackend and do not depend on sqlite connection/cursor types.
backend: DBBackend = SQLiteBackend()

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
    backend.setup_connection(conn)
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
    transaction_token = _composite_transaction_active.set(True)
    try:
        yield
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        _composite_transaction_active.reset(transaction_token)
        if connection_token is not None:
            _request_conn.reset(connection_token)
            conn.close()


def with_db_connection(default_return=None, raise_on_error=True, commit_on_success=True):
    """Inject the current request connection or create a short-lived connection."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            shared_conn = _request_conn.get()
            conn = shared_conn if shared_conn is not None else get_db_connection()
            try:
                result = func(conn, *args, **kwargs)
                if commit_on_success and not _composite_transaction_active.get():
                    conn.commit()
                return result
            except backend.db_error:
                conn.rollback()
                if raise_on_error:
                    raise
                return default_return
            finally:
                if shared_conn is None:
                    conn.close()

        # The connection parameter is an implementation detail injected by this boundary.
        # Public DAO signatures expose only domain arguments.
        function_signature = signature(func)
        wrapper.__signature__ = function_signature.replace(
            parameters=list(function_signature.parameters.values())[1:]
        )
        return wrapper

    return decorator


@with_db_connection()
def init_db(conn):
    backend.init_schema(conn)
