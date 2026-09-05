import sqlite3

from db.backend import DBBackend
from db.sqlite_functions import register_sqlite_functions
from db.sqlite_migration_steps import SQLiteMigrationSteps
from db.sqlite_migrations import Migration, run_migrations
from db.sqlite_schema import create_current_schema

DB_PATH = 'database.db'


class SQLiteBackend(DBBackend):

    def connect(self):
        # check_same_thread=False: с request-scoped переиспользованием соединения (db_connection_
        # per_request в support_planner.py) одно и то же соединение открывается в потоке event loop
        # (внутри @app.middleware('http')), а затем используется синхронными роут-хендлерами,
        # которые FastAPI выполняет в отдельном потоке пула (anyio.to_thread.run_sync) — sqlite3 по
        # умолчанию запрещает такое межпоточное использование одного объекта соединения. Безопасно
        # здесь, поскольку соединение никогда не используется из двух потоков ОДНОВРЕМЕННО — только
        # последовательно в рамках одного запроса (мидлварь -> FastAPI dependencies/роут -> мидлварь).
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
        register_sqlite_functions(conn)

    def last_insert_id(self, cursor) -> int:
        return cursor.lastrowid

    @property
    def db_error(self) -> type:
        return sqlite3.Error

    @property
    def duplicate_error(self) -> type:
        return sqlite3.IntegrityError

    def init_schema(self, conn) -> None:
        steps = SQLiteMigrationSteps()
        migrations = (
            Migration(1, 'employees-to-users', steps.migrate_employees_to_users),
            Migration(2, 'criticality-to-priority', steps.migrate_criticality_to_priority),
            Migration(3, 'restore-criticality', steps.migrate_add_criticality_column),
            Migration(4, 'add-segments', steps.migrate_add_segment_columns),
            Migration(5, 'create-current-schema', create_current_schema),
            Migration(6, 'add-task-completed-at', steps.migrate_add_task_completed_at),
            Migration(7, 'normalize-and-bootstrap', steps.normalize_and_bootstrap),
            Migration(8, 'add-task-completion-template', steps.migrate_add_task_completion_template),
            Migration(9, 'add-task-psi-status', steps.migrate_add_task_psi_status),
            Migration(10, 'add-task-instruction-url', steps.migrate_add_task_instruction_url),
            Migration(11, 'add-new-task-notifications', steps.migrate_add_new_task_notifications),
            Migration(12, 'add-seen-new-task-events', steps.migrate_add_seen_new_task_events),
        )
        run_migrations(conn, migrations)
