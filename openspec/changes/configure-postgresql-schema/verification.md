# Проверка configure-postgresql-schema

Дата: 11 ноября 2026 года.

## Реализовано

- `SUPPORT_PLANNER_DATABASE_SCHEMA` выбирает одну схему; default — `planner`, приоритет окружения над `.env` сохранён. SQLite параметр игнорирует.
- Имя фиксируется в PostgreSQL backend и соединении. Проверяются корректность имени, наличие схемы и право USAGE; автоматическое создание схемы отсутствует.
- Мигратор, журнал, bootstrap, проверки таблиц/индексов/FK, импорт и identity-последовательности используют выбранную схему. Baseline SQL и его checksum не изменены.
- Перенос SQLite сохраняет обычный импорт, dry-run, явную замену, сверку и транзакционные границы. Ошибка конфигурации схемы доступна в CLI и отчёте без DSN.
- Обновлены PostgreSQL fixtures, integration-тесты, UI-harness и инструкции конфигурации/развёртывания.

## Выполненные проверки

Команда из корня репозитория:

```sh
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 SUPPORT_PLANNER_TEST_BACKEND=sqlite \
  .venv/bin/python -m pytest -q \
  tests/test_postgresql_schema.py tests/test_storage_configuration.py \
  tests/test_storage_contract.py tests/test_db_module_boundaries.py \
  tests/test_sqlite_migrations.py tests/test_postgresql_integration.py
```

Результат: **76 passed, 15 skipped**. Пропущены только сценарии, требующие выбранного PostgreSQL backend; эти пропуски не являются PostgreSQL-приёмкой. Конфигурация, экранирование имён, выбор схемы, сохранность baseline, отказ при отсутствии схемы/прав и закрытие соединения проверены unit-тестами. Общие backend-контракты выполнены на SQLite.

Дополнительно расширена проверка явного SQLite CLI: ошибочные PostgreSQL URL и пустой параметр схемы игнорируются при `--database`. Повторный адресный прогон этого теста выполнен отдельно: **1 passed**.

Проверки запущены на **Python 3.9.25**. Изменённые Python-файлы разобраны парсером Python 3.9; UTF-8 без BOM подтверждён. `git diff --check` не выявил ошибок. SHA-256 исходного baseline: `36d4cbfe60a5318bce9ff22d0429685f83d42dd51ad766e58c452033ba6a9ab7`.

Рабочий `database.db` перед тестами отсутствовал; тесты использовали временные SQLite БД. Пользовательская БД не изменялась. Все запущенные тестовые Python-процессы завершились; production-backend не запускался.

## Невыполненная PostgreSQL-приёмка

`SUPPORT_PLANNER_TEST_DATABASE_URL` не задан. Попытка отдельного PostgreSQL-прогона завершилась до сбора тестов с кодом 4 и сообщением `PostgreSQL tests require a separate SUPPORT_PLANNER_TEST_DATABASE_URL; it will be cleared`. Пользователь явно выбрал «Отложить PostgreSQL-проверки»; они остаются невыполненными и не препятствуют передаче подготовленного кода на проверку.

До завершения приёмки необходимо на отдельной PostgreSQL БД с заранее созданной схемой выполнить:

- Общие backend-контракты и integration-тесты для default `planner`, другой схемы и явного `public`.
- Применение baseline, повторный мигратор, права отдельной runtime-роли, отказ без USAGE и отсутствие автоматического создания схемы.
- Первый перенос SQLite, dry-run, повторную замену, rollback, последовательности ID, изоляцию схем и защиту от внешних FK.
- Документированные команды миграции/импорта и production UI с реальным входом, свежей сборкой, pg_dump/pg_restore и проверкой восстановленных данных.

Эти сценарии не заменены моками или SQLite. В tasks.md закрыты **5 из 14** пунктов; остальные содержат реализацию/тесты, но ожидают реального PostgreSQL-прогона. Sync, archive, commit и фактический перенос пользовательских данных не выполнялись.
