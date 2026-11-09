from abc import ABC, abstractmethod


class DBBackend(ABC):

    name = 'sqlite'
    placeholder = '?'
    now_sql = 'CURRENT_TIMESTAMP'

    def placeholders(self, count):
        return ','.join(self.placeholder for _ in range(count))

    def insert_id(self, conn, statement, params=()):
        return self.last_insert_id(conn.execute(statement, params))

    def conflict_ignore(self, columns):
        return ' ON CONFLICT (' + ','.join(columns) + ') DO NOTHING'

    def candidate_cursor(self, conn, query, params):
        return conn.execute(query, params)

    def close(self, conn):
        try:
            if getattr(conn, 'in_transaction', False) is True:
                conn.rollback()
        finally:
            conn.close()

    @abstractmethod
    def begin_write(self, conn) -> None:
        """Начать транзакцию записи до чтения проверяемых ограничений."""

    @abstractmethod
    def connect(self):
        """Вернуть новое соединение с БД."""

    @abstractmethod
    def setup_connection(self, conn) -> None:
        """Настроить соединение после открытия (PRAGMA, функции, курсор и т.п.)."""

    @abstractmethod
    def last_insert_id(self, cursor) -> int:
        """ID последней вставленной строки."""

    @property
    @abstractmethod
    def db_error(self) -> type:
        """Базовый класс ошибок выбранного адаптера."""

    @property
    @abstractmethod
    def duplicate_error(self) -> type:
        """Кандидат нарушения UNIQUE; уточняется через is_unique()."""

    @abstractmethod
    def init_schema(self, conn) -> None:
        """Создать/обновить схему БД (идемпотентно — все DDL через IF NOT EXISTS)."""
