from abc import ABC, abstractmethod


class DBBackend(ABC):

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
        """Базовый класс ошибок драйвера (sqlite3.Error / psycopg2.Error)."""

    @property
    @abstractmethod
    def duplicate_error(self) -> type:
        """Ошибка нарушения UNIQUE (sqlite3.IntegrityError / psycopg2.errors.UniqueViolation)."""

    @abstractmethod
    def init_schema(self, conn) -> None:
        """Создать/обновить схему БД (идемпотентно — все DDL через IF NOT EXISTS)."""
