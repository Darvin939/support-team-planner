import sqlite3

import auth
from db.backend import DBBackend

DB_PATH = 'database.db'

# @formatter:off
_SCHEMA = '''
    CREATE TABLE if NOT EXISTS teams (
        id INTEGER PRIMARY key autoincrement,
        name text NOT NULL UNIQUE
    );

    CREATE TABLE IF NOT EXISTS team_blocks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id INTEGER NOT NULL,
        block_name TEXT NOT NULL,
        schedule_offset INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (team_id) REFERENCES teams (id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_team_blocks_team_id ON team_blocks (team_id);

    CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY key autoincrement,
        last_name TEXT NOT NULL,
        first_name TEXT NOT NULL,
        middle_name TEXT,
        password_hash TEXT,
        role TEXT NOT NULL DEFAULT 'user',
        UNIQUE(last_name, first_name, middle_name)
    );

    CREATE TABLE if NOT EXISTS freeze_days (
        id INTEGER PRIMARY key autoincrement,
        date DATE NOT NULL UNIQUE
    );

    CREATE TABLE if NOT EXISTS tasks (
        id INTEGER PRIMARY key autoincrement,
        team_id INTEGER NOT NULL,
        name text NOT NULL,
        description text,
        criticality text NOT NULL DEFAULT 'medium',
        task_status TEXT NOT NULL DEFAULT 'new',
        is_deleted INTEGER NOT NULL DEFAULT 0,
        FOREIGN key (team_id) REFERENCES teams (id) ON DELETE cascade
    );

    CREATE TABLE if NOT EXISTS assignments (
        id INTEGER PRIMARY key autoincrement,
        task_id INTEGER NOT NULL,
        date DATE NOT NULL,
        block text,
        status text NOT NULL DEFAULT 'new',
        employee_id INTEGER,
        comment text,
        is_psi INTEGER NOT NULL DEFAULT 0,
        time_spent text,
        is_deleted INTEGER NOT NULL DEFAULT 0,
        FOREIGN key (task_id) REFERENCES tasks (id) ON DELETE cascade,
        FOREIGN key (employee_id) REFERENCES employees (id)
    );

    CREATE TABLE IF NOT EXISTS task_dependencies (
        task_id            INTEGER NOT NULL,
        depends_on_task_id INTEGER NOT NULL,
        PRIMARY KEY (task_id, depends_on_task_id),
        FOREIGN KEY (task_id)            REFERENCES tasks(id) ON DELETE CASCADE,
        FOREIGN KEY (depends_on_task_id) REFERENCES tasks(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS blocks (
        id   INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT    NOT NULL UNIQUE
    );

    CREATE TABLE IF NOT EXISTS block_templates (
        id   INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT    NOT NULL UNIQUE
    );

    CREATE TABLE IF NOT EXISTS template_blocks (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        template_id     INTEGER NOT NULL REFERENCES block_templates(id) ON DELETE CASCADE,
        block_id        INTEGER NOT NULL REFERENCES blocks(id)          ON DELETE CASCADE,
        schedule_offset INTEGER NOT NULL DEFAULT 0,
        UNIQUE(template_id, block_id)
    );

    CREATE TABLE IF NOT EXISTS team_templates (
        team_id     INTEGER NOT NULL REFERENCES teams(id)           ON DELETE CASCADE,
        template_id INTEGER NOT NULL REFERENCES block_templates(id) ON DELETE CASCADE,
        PRIMARY KEY(team_id, template_id)
    );

    -- Задачи/назначения теперь не удаляются физически (см. tasks.is_deleted/assignments.is_deleted) — это делает
    -- FK на таблицы истории безопасным: запись истории переживёт "удаление" задачи/назначения, потому что строка
    -- на самом деле никуда не девается. FK на changed_by_employee_id — ON DELETE SET NULL, а не CASCADE: сотрудников
    -- по-прежнему физически удаляют (delete_employee), и запись истории должна остаться, просто без автора.
    CREATE TABLE IF NOT EXISTS task_history (
        id                     INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id                INTEGER NOT NULL,
        action                 TEXT NOT NULL,
        field_name             TEXT,
        old_value              TEXT,
        new_value              TEXT,
        changed_at             TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        changed_by_employee_id INTEGER,
        FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE CASCADE,
        FOREIGN KEY (changed_by_employee_id) REFERENCES employees (id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS assignment_history (
        id                     INTEGER PRIMARY KEY AUTOINCREMENT,
        assignment_id          INTEGER NOT NULL,
        task_id                INTEGER NOT NULL,
        date                   DATE NOT NULL,
        action                 TEXT NOT NULL,
        field_name             TEXT,
        old_value              TEXT,
        new_value              TEXT,
        changed_at             TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        changed_by_employee_id INTEGER,
        FOREIGN KEY (assignment_id) REFERENCES assignments (id) ON DELETE CASCADE,
        FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE CASCADE,
        FOREIGN KEY (changed_by_employee_id) REFERENCES employees (id) ON DELETE SET NULL
    );

    CREATE INDEX IF NOT EXISTS idx_task_history_task_id ON task_history (task_id);
    CREATE INDEX IF NOT EXISTS idx_assignment_history_assignment_id ON assignment_history (assignment_id);
    CREATE INDEX IF NOT EXISTS idx_assignment_history_task_id ON assignment_history (task_id);

    CREATE index if NOT EXISTS idx_assignments_task_id ON assignments (task_id);
    CREATE index if NOT EXISTS idx_assignments_date ON assignments (date);
    CREATE index if NOT EXISTS idx_assignments_status ON assignments (status);
    CREATE index if NOT EXISTS idx_tasks_team_id ON tasks (team_id);
    CREATE UNIQUE INDEX if NOT EXISTS ux_assignments_task_date ON assignments (task_id, date) WHERE is_deleted = 0;
'''
# @formatter:on


def _fuzzy_word_in(text, word):
    """Проверяет, встречается ли word в text с допуском на 1 опечатку (скользящее окно)."""
    if not text or not word:
        return False
    text, word = text.lower(), word.lower()
    if word in text:
        return True
    n = len(word)
    if n < 3:
        return False
    max_errors = max(1, n // 7)
    for i in range(len(text) - n + 1):
        if sum(a != b for a, b in zip(text[i:i + n], word)) <= max_errors:
            return True
    return False


class SQLiteBackend(DBBackend):

    def connect(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def setup_connection(self, conn) -> None:
        conn.execute('PRAGMA foreign_keys = ON;')
        conn.create_function('fuzzy_word_in', 2, _fuzzy_word_in)

    def last_insert_id(self, cursor) -> int:
        return cursor.lastrowid

    @property
    def db_error(self) -> type:
        return sqlite3.Error

    @property
    def duplicate_error(self) -> type:
        return sqlite3.IntegrityError

    def init_schema(self, conn) -> None:
        conn.execute('PRAGMA foreign_keys = ON;')
        conn.executescript(_SCHEMA)
        # Сотрудник по умолчанию для первого входа (пароль можно сменить в настройках).
        # INSERT OR IGNORE полагается на UNIQUE(last_name, first_name, middle_name) — безопасно
        # выполнять при каждом запуске, не создаёт дублей. middle_name='' (не NULL): NULL никогда
        # не считается равным другому NULL в UNIQUE-констрейнте, так что с NULL проверка бы не сработала.
        conn.execute(
            "INSERT OR IGNORE INTO employees (last_name, first_name, middle_name, password_hash, role) VALUES (?, ?, ?, ?, ?)",
            ('Администратор', '', '', auth.hash_password('q12345678'), 'admin')
        )
        conn.commit()
