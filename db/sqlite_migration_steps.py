import sqlite3

import auth


class SQLiteMigrationSteps:
    @staticmethod
    def normalize_and_bootstrap(conn) -> None:
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

    @staticmethod
    def migrate_add_task_completed_at(conn) -> None:
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
    def migrate_employees_to_users(conn) -> None:
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
    def migrate_criticality_to_priority(conn) -> None:
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
            priority = len(rows) * SQLiteMigrationSteps._PRIORITY_GAP
            for row in rows:
                conn.execute('UPDATE tasks SET priority = ? WHERE id = ?', (priority, row['id']))
                priority -= SQLiteMigrationSteps._PRIORITY_GAP

    @staticmethod
    def migrate_add_criticality_column(conn) -> None:
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

    @staticmethod
    def migrate_add_task_completion_template(conn) -> None:
        """Сохраняет шаблон, выбранный для автоназначений работы."""
        columns = {row[1] for row in conn.execute('PRAGMA table_info(tasks)').fetchall()}
        if 'completion_template_id' not in columns:
            conn.execute(
                'ALTER TABLE tasks ADD COLUMN completion_template_id INTEGER '
                'REFERENCES block_templates(id) ON DELETE SET NULL'
            )

    _DEFAULT_SEGMENT_NAME = 'По умолчанию'

    @staticmethod
    def migrate_add_segment_columns(conn) -> None:
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
            'INSERT OR IGNORE INTO segments (name) VALUES (?)', (SQLiteMigrationSteps._DEFAULT_SEGMENT_NAME,)
        )
        default_segment_id = conn.execute(
            'SELECT id FROM segments WHERE name = ?', (SQLiteMigrationSteps._DEFAULT_SEGMENT_NAME,)
        ).fetchone()[0]

        for table in tables_needing_backfill:
            conn.execute(
                f'ALTER TABLE {table} ADD COLUMN segment_id INTEGER NOT NULL '
                f'DEFAULT {int(default_segment_id)} REFERENCES segments(id)'
            )
