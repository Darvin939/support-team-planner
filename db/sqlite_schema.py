# @formatter:off
SCHEMA = '''
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

    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY key autoincrement,
        last_name TEXT,
        first_name TEXT NOT NULL,
        middle_name TEXT,
        password_hash TEXT,
        role TEXT NOT NULL DEFAULT 'user',
        login TEXT,
        is_assignee INTEGER NOT NULL DEFAULT 1
    );

    -- Отдельный UNIQUE-индекс (а не inline UNIQUE в CREATE TABLE) — ALTER TABLE ADD COLUMN в SQLite
    -- не умеет добавлять UNIQUE-колонку к уже существующей таблице, поэтому уникальность login
    -- для мигрируемых БД обеспечивается этим индексом, а не констрейнтом самой колонки.
    CREATE UNIQUE INDEX IF NOT EXISTS idx_users_login ON users (login);

    CREATE TABLE IF NOT EXISTS user_team_access (
        user_id INTEGER NOT NULL,
        team_id INTEGER NOT NULL,
        PRIMARY KEY (user_id, team_id),
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
        FOREIGN KEY (team_id) REFERENCES teams (id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_user_team_access_team_id ON user_team_access (team_id);

    CREATE TABLE if NOT EXISTS freeze_days (
        id INTEGER PRIMARY key autoincrement,
        date DATE NOT NULL UNIQUE
    );

    CREATE TABLE IF NOT EXISTS segments (
        id   INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT    NOT NULL UNIQUE
    );

    CREATE TABLE if NOT EXISTS tasks (
        id INTEGER PRIMARY key autoincrement,
        team_id INTEGER NOT NULL,
        segment_id INTEGER NOT NULL REFERENCES segments(id),
        name text NOT NULL,
        description text,
        criticality text NOT NULL DEFAULT 'medium',
        priority INTEGER NOT NULL DEFAULT 0,
        task_status TEXT NOT NULL DEFAULT 'new',
        psi_status TEXT NOT NULL DEFAULT 'not_required',
        completed_at TEXT,
        completion_template_id INTEGER REFERENCES block_templates(id) ON DELETE SET NULL,
        is_deleted INTEGER NOT NULL DEFAULT 0,
        FOREIGN key (team_id) REFERENCES teams (id) ON DELETE cascade
    );

    CREATE TABLE if NOT EXISTS assignments (
        id INTEGER PRIMARY key autoincrement,
        task_id INTEGER NOT NULL,
        date DATE NOT NULL,
        block text,
        status text NOT NULL DEFAULT 'new',
        user_id INTEGER,
        comment text,
        is_psi INTEGER NOT NULL DEFAULT 0,
        time_spent text,
        is_deleted INTEGER NOT NULL DEFAULT 0,
        FOREIGN key (task_id) REFERENCES tasks (id) ON DELETE cascade,
        FOREIGN key (user_id) REFERENCES users (id)
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
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        name       TEXT    NOT NULL UNIQUE,
        segment_id INTEGER NOT NULL REFERENCES segments(id)
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
    -- на самом деле никуда не девается. FK на changed_by_user_id — ON DELETE SET NULL, а не CASCADE: пользователей
    -- по-прежнему физически удаляют (delete_user), и запись истории должна остаться, просто без автора.
    CREATE TABLE IF NOT EXISTS task_history (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id            INTEGER NOT NULL,
        action             TEXT NOT NULL,
        field_name         TEXT,
        old_value          TEXT,
        new_value          TEXT,
        changed_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        changed_by_user_id INTEGER,
        FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE CASCADE,
        FOREIGN KEY (changed_by_user_id) REFERENCES users (id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS assignment_history (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        assignment_id      INTEGER NOT NULL,
        task_id            INTEGER NOT NULL,
        date               DATE NOT NULL,
        action             TEXT NOT NULL,
        field_name         TEXT,
        old_value          TEXT,
        new_value          TEXT,
        changed_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        changed_by_user_id INTEGER,
        FOREIGN KEY (assignment_id) REFERENCES assignments (id) ON DELETE CASCADE,
        FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE CASCADE,
        FOREIGN KEY (changed_by_user_id) REFERENCES users (id) ON DELETE SET NULL
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


def create_current_schema(conn) -> None:
    conn.execute('PRAGMA foreign_keys = ON;')
    conn.executescript(SCHEMA)
