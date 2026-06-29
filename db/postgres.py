import re

import psycopg2
import psycopg2.errors
import psycopg2.extras

from db.backend import DBBackend

# PL/pgSQL реализация того же алгоритма скользящего окна, что и _fuzzy_word_in в db/sqlite.py
_FUZZY_WORD_IN_SQL = """
CREATE OR REPLACE FUNCTION fuzzy_word_in(text_val TEXT, word TEXT)
RETURNS BOOLEAN AS $$
DECLARE
    tl TEXT;
    wl TEXT;
    n INT;
    max_errors INT;
    i INT;
    j INT;
    errors INT;
BEGIN
    IF text_val IS NULL OR word IS NULL THEN RETURN FALSE; END IF;
    tl := lower(text_val);
    wl := lower(word);
    IF strpos(tl, wl) > 0 THEN RETURN TRUE; END IF;
    n := length(wl);
    IF n < 3 THEN RETURN FALSE; END IF;
    max_errors := GREATEST(1, n / 7);
    FOR i IN 1..(length(tl) - n + 1) LOOP
        errors := 0;
        FOR j IN 1..n LOOP
            IF substr(tl, i + j - 1, 1) <> substr(wl, j, 1) THEN
                errors := errors + 1;
            END IF;
        END LOOP;
        IF errors <= max_errors THEN RETURN TRUE; END IF;
    END LOOP;
    RETURN FALSE;
END;
$$ LANGUAGE plpgsql IMMUTABLE;
"""

# @formatter:off
_PG_SCHEMA_STMTS = [
    """CREATE TABLE IF NOT EXISTS teams (
        id   SERIAL PRIMARY KEY,
        name TEXT NOT NULL UNIQUE
    )""",

    """CREATE TABLE IF NOT EXISTS team_blocks (
        id              SERIAL PRIMARY KEY,
        team_id         INTEGER NOT NULL,
        block_name      TEXT NOT NULL,
        schedule_offset INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (team_id) REFERENCES teams (id) ON DELETE CASCADE
    )""",
    "CREATE INDEX IF NOT EXISTS idx_team_blocks_team_id ON team_blocks (team_id)",

    """CREATE TABLE IF NOT EXISTS employees (
        id          SERIAL PRIMARY KEY,
        last_name   TEXT NOT NULL,
        first_name  TEXT NOT NULL,
        middle_name TEXT,
        UNIQUE (last_name, first_name, middle_name)
    )""",

    """CREATE TABLE IF NOT EXISTS freeze_days (
        id   SERIAL PRIMARY KEY,
        date DATE NOT NULL UNIQUE
    )""",

    """CREATE TABLE IF NOT EXISTS tasks (
        id          SERIAL PRIMARY KEY,
        team_id     INTEGER NOT NULL,
        name        TEXT NOT NULL,
        description TEXT,
        criticality TEXT NOT NULL DEFAULT 'medium',
        task_status TEXT NOT NULL DEFAULT 'new',
        FOREIGN KEY (team_id) REFERENCES teams (id) ON DELETE CASCADE
    )""",
    "CREATE INDEX IF NOT EXISTS idx_tasks_team_id ON tasks (team_id)",

    """CREATE TABLE IF NOT EXISTS assignments (
        id          SERIAL PRIMARY KEY,
        task_id     INTEGER NOT NULL,
        date        DATE NOT NULL,
        block       TEXT,
        status      TEXT NOT NULL DEFAULT 'new',
        employee_id INTEGER,
        comment     TEXT,
        FOREIGN KEY (task_id)     REFERENCES tasks (id)     ON DELETE CASCADE,
        FOREIGN KEY (employee_id) REFERENCES employees (id),
        UNIQUE (task_id, date)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_assignments_task_id ON assignments (task_id)",
    "CREATE INDEX IF NOT EXISTS idx_assignments_date    ON assignments (date)",
    "CREATE INDEX IF NOT EXISTS idx_assignments_status  ON assignments (status)",

    """CREATE TABLE IF NOT EXISTS task_dependencies (
        task_id            INTEGER NOT NULL,
        depends_on_task_id INTEGER NOT NULL,
        PRIMARY KEY (task_id, depends_on_task_id),
        FOREIGN KEY (task_id)            REFERENCES tasks (id) ON DELETE CASCADE,
        FOREIGN KEY (depends_on_task_id) REFERENCES tasks (id) ON DELETE CASCADE
    )""",
]
# @formatter:on


def _adapt_sql(sql: str) -> str:
    """Конвертирует SQLite-диалект SQL в PostgreSQL:
    - `?` → `%s`
    - `INSERT OR IGNORE INTO X` → `INSERT INTO X ... ON CONFLICT DO NOTHING`
    """
    adapted = sql.replace('?', '%s')
    if re.search(r'INSERT\s+OR\s+IGNORE', adapted, re.IGNORECASE):
        adapted = re.sub(
            r'INSERT\s+OR\s+IGNORE\s+INTO',
            'INSERT INTO',
            adapted,
            flags=re.IGNORECASE,
        )
        adapted = adapted.rstrip() + ' ON CONFLICT DO NOTHING'
    return adapted


class _PgCursor:
    """Обёртка psycopg2-курсора — имитирует поведение sqlite3.Cursor."""

    def __init__(self, cur):
        self._cur = cur

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def __iter__(self):
        return iter(self._cur)


class _PgConnectionWrapper:
    """Обёртка psycopg2-соединения — имитирует интерфейс sqlite3.Connection,
    включая `conn.execute()`, адаптацию SQL-диалекта и DictCursor."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=()):
        adapted = _adapt_sql(sql)
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute(adapted, params or ())
        return _PgCursor(cur)

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()

    def rollback(self):
        self._conn.rollback()


class PostgresBackend(DBBackend):

    def __init__(self, **kwargs):
        """kwargs передаются напрямую в psycopg2.connect().
        Если не переданы — psycopg2 читает стандартные PG* env-vars.
        Пример: PostgresBackend(host='localhost', dbname='mydb', user='postgres')
        """
        self._kwargs = kwargs

    def connect(self):
        conn = psycopg2.connect(**self._kwargs) if self._kwargs else psycopg2.connect()
        conn.autocommit = False
        return _PgConnectionWrapper(conn)

    def setup_connection(self, conn) -> None:
        pass  # FK в PostgreSQL включены по умолчанию

    def last_insert_id(self, cursor) -> int:
        cursor._cur.execute("SELECT lastval()")
        return cursor._cur.fetchone()[0]

    @property
    def db_error(self) -> type:
        return psycopg2.Error

    @property
    def duplicate_error(self) -> type:
        return psycopg2.errors.UniqueViolation

    def init_schema(self, conn) -> None:
        conn.execute(_FUZZY_WORD_IN_SQL)
        for stmt in _PG_SCHEMA_STMTS:
            conn.execute(stmt)
