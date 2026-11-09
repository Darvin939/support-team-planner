# Проверка реализации add-postgresql-backend

Дата: 2026-11-09. Исходный HEAD: `d84cd566`. Пользователь разрешил apply и отдельно подтвердил: реализацию и SQLite-проверки продолжать, PostgreSQL проверять позже. Рабочие данные и развёртывание не переключались. Sync, archive и commit не выполнялись.

## Реализовано

- Ранняя загрузка настроек, приоритет PostgreSQL URL, отсутствие fallback, безопасные ошибки; пример `.env.example` без паролей.
- Psycopg 3.2, совместимые строки результата (индекс, имя, dict и последовательность значений), явные параметры/insert ID/conflict-ignore, классификация ограничений.
- PostgreSQL baseline всех 19 таблиц SQLite v15, C collation, BIGINT identity, текстовые даты, прежние FK/индексы; независимый manifest с checksum и session migration lock. Startup только проверяет схему.
- Один connection на запрос, connect/cleanup в worker thread, rollback при любом исключении, явные write DAO, блокировка до guard-чтений и запрет commit после подавленного сбоя composite.
- Переносимые DAO, общая fuzzy/Unicode-семантика, PostgreSQL server cursors с чтением кандидатов пакетами и фильтрация ID до count/pagination.
- CLI `import_sqlite_to_postgres`: новый WAL-safe backup и рабочая копия на каждый запуск, source preflight, dry-run, явная полная замена, ограниченный TRUNCATE без CASCADE, загрузка/сверка/restart sequences одной транзакцией, отчёт с неопределённым commit без автоповтора.
- Demo-генераторы, production UI-harness, отдельные test URL/роли, эксплуатационная инструкция и allowlist дистрибутива.

Наличие кода не считается подтверждением PostgreSQL-приёмки. Чекбоксы задач с обязательной PostgreSQL-проверкой оставлены открытыми.

## Окружение

- Python 3.9.25, Psycopg 3.2.13, pytest 8.4.2.
- FastAPI 0.128.8, Starlette 0.49.3.
- Frontend build: локальный Node 20.19.5. DOM-тесты: Node 24.22.2, поскольку установленный jsdom не запускается на Node 20.
- Production UI: Playwright 1.60.0 и установленный Chrome (Chromium engine), канал `chrome`. Backend запускается тем же Python 3.9, авторизация реальная.
- PostgreSQL-назначение не предоставлено; по решению пользователя сервер не устанавливался и PostgreSQL-прогон не выполнялся.

## Backend

```sh
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 .venv/bin/python -m pytest -q --disable-warnings
```

Финальный полный результат: **206 passed, 8 failed, 8 skipped**, 72.12 с. Восемь skips — явно помеченные PostgreSQL integration-тесты, а не успешные проверки.

Восемь failures воспроизведены в отдельной временной распаковке исходного `git archive HEAD`, с той же production frontend-сборкой и Python-зависимостями: **17 passed, 8 failed**. Это:

- Один route-policy audit в `test_access_control.py`, ожидающий `original_router` у маршрутов.
- Три теста `generate_build_id` в `test_app_metadata.py`, передающие отсутствующий `build_time`.
- Четыре теста `test_release_change_log.py`, ожидающие одну запись журнала при трёх фактически поставляемых версиях.

Эти исходные расхождения не исправлялись в рамках переезда БД. Новых падений полного набора нет. Первоначальное дополнительное падение SQLite CLI исправлено: прежний `user_version=15` в выводе сохранён. После последнего уточнения совместимости Row отдельно повторён `test_storage_configuration.py`: **12 passed**, 8.78 с.

Проверены конфигурация/приоритет/отсутствие fallback, DSN с контрольным паролем в traceback/stdout/stderr, Python 3.9 import Psycopg, row access, прежний SQLite CLI, целевые конфликты, FK/domain ошибки, rollback и повторная запись, подавленный сбой composite, search/ACL/архив/история, match после первого пакета из 1000 кандидатов, пустые фильтры, статистика, назначения и обмен датами, реальный login/API, одно соединение и отсутствие соединения для assets, write lock у GET уведомлений и отсутствие lock у getters.

Источник переноса проверен через настоящий SQLite backup API: committed WAL попадает в новый снимок, два запуска создают разные копии, source не меняется; старая v6 рабочая копия мигрирует до v15 без добавленного администратора, слишком новая версия отказывает до подключения назначения, NUL/неверные типы отклоняются без вывода чувствительных значений. Повреждённый файл, утраченный UNIQUE-индекс с дублем и утраченный FK с осиротевшей строкой также отклоняются до подключения назначения. Связи и уникальность проверяются по manifest независимо от наличия ограничений в SQLite. Manifest сопоставлен с полной схемой SQLite v15.

Отдельно проверен отказ PostgreSQL pytest без `SUPPORT_PLANNER_TEST_DATABASE_URL`: рабочий URL не используется как default. Исторические unittest и pytest тесты собираются единым pytest runner. Старые fixtures с прямым sqlite3/DB_PATH остаются SQLite-specific и явно пропускаются в PostgreSQL-режиме; это ограничение покрытия. Общая новая матрица — `test_storage_contract.py`, миграции/импорт/сбои PostgreSQL — `test_postgresql_integration.py`. Перед production нужно выполнить реальную матрицу и расширить/перенести оставшееся релевантное legacy-покрытие по её результатам.

Локальные логи: `.tmp/backend-final.log`, `.tmp/configuration-final.log`, `.tmp/baseline-tests.log`.

## Frontend и production UI

```sh
cd frontend
npm ci
npm run build
npm exec --yes --package=node@24 -- node node_modules/vitest/vitest.mjs run --maxWorkers=2
npm exec --yes --package=node@24 -- node node_modules/vitest/vitest.mjs run src/pages/settings/BlocksTab.test.tsx src/pages/planning/AssignmentModal.rollout.test.tsx --maxWorkers=1 --testTimeout=60000
```

Production build успешен. В общем Vitest-прогоне: **195 passed, 3 timeout**, 47 файлов. Все упавшие тесты затем прошли в отдельном прогоне двух файлов: **10 passed**. Итого все 198 frontend-тестов имеют успешный результат; отдельный повтор потребовался из-за таймаутов. Frontend-исходники и зависимости не менялись.

```sh
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 PYTHONPATH=. SUPPORT_PLANNER_UI_BROWSER_CHANNEL=chrome .venv/bin/python tests/ui_storage_matrix.py
```

Успешный production SQLite прогон включает реальный вход администратора, редактора и пользователя, проверку запрета админских действий, планирование, bulk-reschedule туда/обратно, SPA-переходы журнала/статистики/планирования с ожиданием DOM, архив, историю, уведомления, desktop 1440×1000 и mobile 390×844 без переполнения. Browser errors отсутствуют. Screenshots просмотрены.

Перед UI выполнена свежая production-сборка; Vite/dev-server не использовался. В checkout отсутствовала `database.db`, поэтому harness работал с отдельной временной SQLite БД, создал backup и восстановил её через SQLite backup API с checkpoint/проверкой. Корневой `database.db` не создавался. Все запущенные backend остановлены в finally, посторонние процессы не останавливались.

Артефакты успешного расширенного UI-прогона: `.tmp/storage-ui-20261109T114826Z-210a3fb2/`; текстовый итог `.tmp/ui-final.log`.

## Инструменты и дистрибутив

Оба генератора выполнены на отдельных временных SQLite БД:

- `scripts.seed_demo_data`: users=11, teams=1, tasks=15, assignments=45.
- `scripts.seed_large_demo_data --teams 2 --tasks 30 --assignments-per-task 2 --batch-size 10 --yes`: users=5, teams=2, tasks=30, assignments=60.

Обе БД прошли quick_check и foreign_key_check. Большой генератор удерживает общую блокировку и одну транзакцию; пакеты не фиксируют промежуточные состояния. PostgreSQL требует migration-роли для restart sequences, как описано в инструкции.

```sh
bash build-distribution.sh --output build/verification-postgresql
```

Финальная сборка успешна, ZIP содержит 102 записи. Проверены новые backend/SQL/manifest/CLI/инструкции, отсутствие тестов/OpenSpec/UI-harness/verify-скриптов, БД, backup/dump, логов, `.env`, node_modules и frontend-исходников. Убрана зависимость сборщика от отсутствующего на macOS `realpath`; разрешение пути выполняется Python.

Из выходного каталога под Python 3.9 успешно выполнены SQLite pre-deploy до `user_version=15`, `scripts.import_sqlite_to_postgres --help`, импорт PostgreSQL-адаптера и чтение manifest. Результат: `build/verification-postgresql/`, `build/verification-postgresql.zip`; лог `.tmp/distribution-build.log`.

Также успешны Python 3.9 compileall, `bash -n`, `git diff --check` и `openspec validate add-postgresql-backend --strict`.

## Незавершённая приёмка

Остаются обязательными на настоящем PostgreSQL 15:

- Полная применимая backend/UI-матрица, startup под runtime-ролью без DDL, реальные ограничения, серверные курсоры, конкурентные writers/миграторы и время событий после ожидания.
- Первичный и повторный перенос копии рабочих данных, сверка всех 19 таблиц, dry-run, высокие/разреженные ID, полное удаление тестовых изменений и fault-сценарии с откатом данных/sequences и неопределённым commit.
- Замеры переноса/широкого поиска, PostgreSQL dump/restore, независимые параллельные экземпляры и сессии.
- Параметры рабочего назначения, роли, адреса, отключение автоперезапусков, окно и приёмка оператора; затем финальный новый снимок и рабочее переключение.

Готовность к production-переключению не подтверждена. Изменение остаётся открытым; sync/archive/commit потребуют отдельных разрешений по AGENTS.md, архивировать незавершённую приёмку нельзя.
