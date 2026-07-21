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
        completed_at TEXT,
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
        # check_same_thread=False: с request-scoped переиспользованием соединения (db_connection_
        # per_request в support_planner.py) одно и то же соединение открывается в потоке event loop
        # (внутри @app.middleware('http')), а затем используется синхронными роут-хендлерами,
        # которые FastAPI выполняет в отдельном потоке пула (anyio.to_thread.run_sync) — sqlite3 по
        # умолчанию запрещает такое межпоточное использование одного объекта соединения. Безопасно
        # здесь, поскольку соединение никогда не используется из двух потоков ОДНОВРЕМЕННО — только
        # последовательно в рамках одного запроса (мидлварь -> require_login -> роут -> мидлварь).
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def setup_connection(self, conn) -> None:
        conn.execute('PRAGMA foreign_keys = ON;')
        # WAL: читатели не блокируются на время записи (важно теперь, когда одно соединение
        # держится на весь HTTP-запрос — см. db_connection_per_request в support_planner.py).
        # synchronous=NORMAL — рекомендуемая для WAL пара: при падении ОС (не приложения) можно
        # потерять самый последний коммит, но сам файл БД повредиться не может; полный fsync на
        # каждую запись (FULL) для внутреннего инструмента планирования избыточен.
        conn.execute('PRAGMA journal_mode=WAL;')
        conn.execute('PRAGMA synchronous=NORMAL;')
        conn.create_function('fuzzy_word_in', 2, _fuzzy_word_in)
        conn.create_function('casefold', 1, lambda value: (value or '').casefold(), deterministic=True)

    def last_insert_id(self, cursor) -> int:
        return cursor.lastrowid

    @property
    def db_error(self) -> type:
        return sqlite3.Error

    @property
    def duplicate_error(self) -> type:
        return sqlite3.IntegrityError

    def init_schema(self, conn) -> None:
        self._migrate_employees_to_users(conn)
        self._migrate_criticality_to_priority(conn)
        self._migrate_add_criticality_column(conn)
        self._migrate_add_segment_columns(conn)
        conn.execute('PRAGMA foreign_keys = ON;')
        conn.executescript(_SCHEMA)
        self._migrate_add_task_completed_at(conn)
        # Промежуточные статусы задачи (ready/in_progress) упразднены — у задачи остаётся только
        # единое активное состояние (new) и терминальные (done/cancelled). Безусловно, при каждом
        # старте: это нормализация значений, а не разовый бэкфилл, повторный запуск безопасен.
        conn.execute("UPDATE tasks SET task_status = 'new' WHERE task_status IN ('ready', 'in_progress')")
        # Миграция для БД, где бутстрап-админ ещё хранится по старой схеме имени
        # (last_name='Администратор', first_name/middle_name пустые) — переносим на новую, где
        # имя администратора хранится только в first_name, а last_name/middle_name = NULL (это
        # системная запись, а не сотрудник поддержки, у которого была бы фамилия).
        conn.execute(
            "UPDATE users SET last_name = NULL, first_name = 'Администратор', middle_name = NULL "
            "WHERE last_name = 'Администратор' AND (first_name IS NULL OR first_name = '') "
            "AND (middle_name IS NULL OR middle_name = '')"
        )
        # Бэкфилл login для БД, созданных до появления этой колонки: находим бутстрап-запись по
        # историческому маркеру имени (пока это единственный признак, раз login ещё не проставлен)
        # и проставляем login='admin', только если он ещё не задан — не затираем логин, который уже
        # сменили в настройках. С этого момента и далее опознаём бутстрап-админа только по
        # login='admin' (см. _is_bootstrap_admin в db/__init__.py) — ФИО для этого больше не
        # используются нигде, включая код ниже.
        conn.execute(
            "UPDATE users SET login = 'admin' WHERE first_name = 'Администратор' "
            "AND (last_name IS NULL OR last_name = '') AND (middle_name IS NULL OR middle_name = '') AND login IS NULL"
        )
        # Пользователь по умолчанию для первого входа (пароль можно сменить в настройках).
        # Раньше полагались на INSERT OR IGNORE + UNIQUE(last_name, first_name, middle_name) для
        # идемпотентности; эта уникальность больше не гарантируется (ФИО теперь не уникальны для
        # обычных пользователей), поэтому здесь явная проверка существования по login.
        existing_admin = conn.execute("SELECT id FROM users WHERE login = 'admin'").fetchone()
        if not existing_admin:
            # is_assignee=0 — учётная запись администратора по умолчанию не является исполнителем
            # назначений (это системная запись, а не сотрудник поддержки), и переключатель
            # is_assignee для неё скрыт в UI (см. isEditingProtected в UsersTab.tsx), так что
            # изменить это через приложение невозможно.
            conn.execute(
                "INSERT INTO users (last_name, first_name, middle_name, password_hash, role, login, is_assignee) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (None, 'Администратор', None, auth.hash_password('q12345678'), 'admin', 'admin', 0)
            )
        # Бэкфилл для БД, где админ был создан/мигрирован до появления этого правила (is_assignee
        # тогда по умолчанию проставлялся в 1 для всех существующих строк) — безусловно, так как
        # изменить это значение через UI для защищённой записи невозможно, а значит 1 здесь может
        # быть только следствием миграции, а не осознанным выбором.
        conn.execute("UPDATE users SET is_assignee = 0 WHERE login = 'admin'")
        conn.commit()

    @staticmethod
    def _migrate_add_task_completed_at(conn) -> None:
        """Add the completion timestamp once and backfill only trustworthy history."""
        columns = {row[1] for row in conn.execute('PRAGMA table_info(tasks)').fetchall()}
        if 'completed_at' not in columns:
            conn.execute('ALTER TABLE tasks ADD COLUMN completed_at TEXT')
            conn.execute('''
                UPDATE tasks
                   SET completed_at = (
                       SELECT MAX(th.changed_at)
                         FROM task_history th
                        WHERE th.task_id = tasks.id
                          AND th.field_name = 'task_status'
                          AND th.new_value IN ('done', 'cancelled')
                   )
                 WHERE task_status IN ('done', 'cancelled')
            ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_tasks_team_completed_at ON tasks (team_id, completed_at)')

    @staticmethod
    def _migrate_employees_to_users(conn) -> None:
        """Переносит БД, созданные до переименования employees -> users, на новую схему:
        переименование таблицы/колонок, отказ от UNIQUE(last_name, first_name, middle_name)
        (уникален теперь только login) и добавление is_assignee. Идемпотентно — безопасно
        выполнять на каждом запуске, каждый шаг сам проверяет, нужен ли он ещё.

        Отключаем PRAGMA foreign_keys на время миграции: при её включённом состоянии DROP TABLE
        выполняет неявный DELETE всех строк таблицы перед удалением, что запускает проверку FK —
        и падает с FOREIGN KEY constraint failed, потому что assignments.user_id ссылается на
        users(id) без ON DELETE. Включаем обратно в конце, до создания/заполнения остальной схемы."""
        conn.execute('PRAGMA foreign_keys = OFF;')

        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}

        if 'employees' in tables:
            # Миграция для БД, созданных до появления колонки login — SQLite не поддерживает
            # ADD COLUMN IF NOT EXISTS, поэтому глушим ошибку "duplicate column" на уже
            # мигрированных БД.
            try:
                conn.execute('ALTER TABLE employees ADD COLUMN login TEXT')
            except sqlite3.OperationalError:
                pass
            if 'users' not in tables:
                # SQLite сам переписывает REFERENCES employees(...) на REFERENCES users(...)
                # во всех остальных таблицах схемы при переименовании таблицы.
                conn.execute('ALTER TABLE employees RENAME TO users')
                tables.discard('employees')
                tables.add('users')

        if 'users' in tables:
            columns = {row[1] for row in conn.execute('PRAGMA table_info(users)').fetchall()}
            if 'is_assignee' not in columns:
                # Отказ от UNIQUE(last_name, first_name, middle_name) и NOT NULL на last_name
                # требует пересоздания таблицы — ALTER TABLE в SQLite не умеет менять констрейнты.
                conn.execute('DROP TABLE IF EXISTS users_new')
                conn.execute('''
                    CREATE TABLE users_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        last_name TEXT,
                        first_name TEXT NOT NULL,
                        middle_name TEXT,
                        password_hash TEXT,
                        role TEXT NOT NULL DEFAULT 'user',
                        login TEXT,
                        is_assignee INTEGER NOT NULL DEFAULT 1
                    )
                ''')
                conn.execute('''
                    INSERT INTO users_new (id, last_name, first_name, middle_name, password_hash, role, login, is_assignee)
                    SELECT id, last_name, first_name, middle_name, password_hash, role, login, 1 FROM users
                ''')
                conn.execute('DROP TABLE users')
                conn.execute('ALTER TABLE users_new RENAME TO users')
                conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_users_login ON users (login)')

        if 'assignments' in tables:
            cols = {row[1] for row in conn.execute('PRAGMA table_info(assignments)').fetchall()}
            if 'employee_id' in cols:
                conn.execute('ALTER TABLE assignments RENAME COLUMN employee_id TO user_id')

        for hist_table in ('task_history', 'assignment_history'):
            if hist_table in tables:
                cols = {row[1] for row in conn.execute(f'PRAGMA table_info({hist_table})').fetchall()}
                if 'changed_by_employee_id' in cols:
                    conn.execute(f'ALTER TABLE {hist_table} RENAME COLUMN changed_by_employee_id TO changed_by_user_id')

    _PRIORITY_GAP = 1000

    @staticmethod
    def _migrate_criticality_to_priority(conn) -> None:
        """Переносит tasks.criticality (упразднённое 3-уровневое поле) на числовой priority —
        непрерывный, полностью ручной ключ сортировки. ALTER TABLE ADD COLUMN — единственный
        способ добавить колонку в SQLite без пересоздания таблицы; try/except нужен потому что
        SQLite не поддерживает ADD COLUMN IF NOT EXISTS (тот же приём, что и для login выше).

        Бэкфилл выполняется только в ветке, где priority ещё отсутствовал (т.е. строго один раз
        за всю жизнь БД) — если запускать его на каждом старте, он затирал бы priority, который
        пользователи уже вручную переставили через drag-and-drop/контекстное меню.

        Присваиваем старым задачам убывающую последовательность (шаг _PRIORITY_GAP), обходя
        каждую команду в том же порядке, в котором задачи сортировались до этой миграции
        (criticality high/medium/low, затем task_status in_progress/ready/new/done/cancelled,
        затем id) — так, чтобы порядок на экране не менялся сразу после деплоя."""
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if 'tasks' not in tables:
            return  # совсем свежая БД — priority появится через _SCHEMA ниже

        columns = {row[1] for row in conn.execute('PRAGMA table_info(tasks)').fetchall()}
        if 'priority' in columns:
            return  # уже мигрировано

        conn.execute('ALTER TABLE tasks ADD COLUMN priority INTEGER NOT NULL DEFAULT 0')

        if 'criticality' not in columns:
            return  # не должно случиться (priority отсутствовал => старая схема), но защитный выход

        for (team_id,) in conn.execute('SELECT id FROM teams').fetchall():
            rows = conn.execute(
                '''SELECT id FROM tasks WHERE team_id = ?
                   ORDER BY CASE criticality WHEN 'high' THEN 0 WHEN 'medium' THEN 1 WHEN 'low' THEN 2 ELSE 3 END,
                            CASE task_status WHEN 'in_progress' THEN 0 WHEN 'ready' THEN 1 WHEN 'new' THEN 2
                                             WHEN 'done' THEN 3 WHEN 'cancelled' THEN 4 ELSE 5 END,
                            id''',
                (team_id,)
            ).fetchall()
            priority = len(rows) * SQLiteBackend._PRIORITY_GAP
            for row in rows:
                conn.execute('UPDATE tasks SET priority = ? WHERE id = ?', (priority, row['id']))
                priority -= SQLiteBackend._PRIORITY_GAP

    @staticmethod
    def _migrate_add_criticality_column(conn) -> None:
        """Возвращает tasks.criticality на БД, созданных в промежутке, пока критичность была
        упразднена (после однократного переноса в _migrate_criticality_to_priority ниже колонка в
        схеме отсутствовала вовсе) — у таких БД есть priority, но нет criticality. БД старше этого
        промежутка уже имеют criticality (она никогда физически не удалялась), а свежие БД получают
        её через _SCHEMA. try/except не нужен: колонка уже проверяется через PRAGMA перед ALTER."""
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if 'tasks' not in tables:
            return  # совсем свежая БД — criticality появится через _SCHEMA ниже

        columns = {row[1] for row in conn.execute('PRAGMA table_info(tasks)').fetchall()}
        if 'criticality' in columns:
            return  # уже есть (либо никогда не удалялась, либо уже мигрировано)

        conn.execute("ALTER TABLE tasks ADD COLUMN criticality TEXT NOT NULL DEFAULT 'medium'")

    _DEFAULT_SEGMENT_NAME = 'По умолчанию'

    @staticmethod
    def _migrate_add_segment_columns(conn) -> None:
        """Бэкфилл segment_id на БД, созданных до появления сегментов: для каждой из block_templates
        и tasks, если таблица уже существует и в ней ещё нет колонки segment_id, добавляем её как
        NOT NULL DEFAULT <id сегмента по умолчанию> — SQLite применяет DEFAULT к уже существующим
        строкам при ADD COLUMN NOT NULL, так что бэкфилл происходит тем же выражением.

        Сегмент "По умолчанию" создаётся здесь же, но только если он реально понадобится для
        бэкфилла хотя бы одной из этих таблиц — на совсем свежей БД (обе таблицы ещё не существуют)
        и на уже мигрированной (колонка уже есть) сегмент по умолчанию не создаётся вовсе: заводить
        первый сегмент в таком случае — дело пользователя через настройки, а не миграции."""
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        tables_needing_backfill = []
        for table in ('block_templates', 'tasks'):
            if table not in tables:
                continue  # совсем свежая БД — segment_id появится через _SCHEMA ниже
            columns = {row[1] for row in conn.execute(f'PRAGMA table_info({table})').fetchall()}
            if 'segment_id' not in columns:
                tables_needing_backfill.append(table)

        if not tables_needing_backfill:
            return  # мигрировать нечего — либо свежая БД, либо уже мигрировано ранее

        conn.execute('''
            CREATE TABLE IF NOT EXISTS segments (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT    NOT NULL UNIQUE
            )
        ''')
        conn.execute(
            'INSERT OR IGNORE INTO segments (name) VALUES (?)', (SQLiteBackend._DEFAULT_SEGMENT_NAME,)
        )
        default_segment_id = conn.execute(
            'SELECT id FROM segments WHERE name = ?', (SQLiteBackend._DEFAULT_SEGMENT_NAME,)
        ).fetchone()[0]

        for table in tables_needing_backfill:
            conn.execute(
                f'ALTER TABLE {table} ADD COLUMN segment_id INTEGER NOT NULL '
                f'DEFAULT {int(default_segment_id)} REFERENCES segments(id)'
            )
