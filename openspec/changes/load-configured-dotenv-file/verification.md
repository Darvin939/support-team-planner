# Проверка загрузки явно выбранного dotenv-файла

## Реализация

Settings загружает один UTF-8 dotenv-файл из `SUPPORT_PLANNER_ENV_FILE` до выбора хранилища. Окружение имеет приоритет; интерполяция внешнего файла отключена, ошибки чтения останавливают startup. Без переменной стандартная загрузка `.env` сохранена; skip-флаг отключает оба режима. TLS-модуль повторно dotenv не читает.

Shell-entrypoint и его тесты удалены. Dockerfile, `.dockerignore` и `build-distribution.sh` совпадают с исходным состоянием до этого изменения. README, POSTGRESQL.md и `.env.example` описывают один dotenv-файл по пути из примера пользователя.

## Тесты Python 3.9

```sh
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 SUPPORT_PLANNER_SKIP_DOTENV=1 .venv/bin/python -m unittest discover -s tests -p test_settings.py -v
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 SUPPORT_PLANNER_SKIP_DOTENV=1 SUPPORT_PLANNER_TEST_BACKEND=sqlite .venv/bin/python -m pytest -q tests/test_settings.py tests/test_postgresql_schema.py tests/test_storage_configuration.py
```

Python **3.9.25**: отдельно прошли **12 новых unit-тестов**; общий целевой pytest-прогон, включающий эти тесты, — **56 passed**, пропусков нет.

Проверены явный путь с пробелами, приоритет окружения и пустых значений, буквальные `${...}`/`$()` и корректное dotenv-экранирование, стандартный поиск и прежняя интерполяция, отсутствие дополнения из локального `.env`, skip-флаг, пустой допустимый файл, отсутствующий/нечитаемый файл, пустой путь, каталог, некорректный UTF-8, единая загрузка с TLS и выбор PostgreSQL до прикладных импортов без подключения. Недоступный файл останавливает импорт до открытия SQLite; содержимое секретов не попадает в ошибку.

Новые тесты изолируют окружение и выполняют копию settings во временном каталоге. Существующие storage-тесты используют свои временные SQLite-файлы. Рабочая БД и реальные PostgreSQL-реквизиты не использовались. Все созданные Python-процессы завершились.

## Свежий дистрибутив

```sh
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 .venv/bin/python .tmp/verify_settings_dotenv.py
```

Сценарий выполнил свежую production-сборку frontend через `build-distribution.sh --output .tmp/settings-verification-72dmh9s2/distribution` и распаковал ZIP штатным `unzip`.

- **96 файлов**: каталог, ZIP и распакованная поставка побайтно совпадают; settings и TLS-модуль совпадают с текущими исходниками.
- Shell-wrapper отсутствует; Dockerfile сохраняет прямой CMD Python. Все COPY-исходники присутствуют, кроме отдельно предоставляемого пользователем `pip.conf`.
- В поставке нет локальных dotenv, БД, backups, логов, `pip.conf`, тестов, OpenSpec и development-каталогов.
- YAML из README разобран. Его правила экранирования применены к фиктивным Vault-значениям; распакованное приложение через settings загрузило точные URL, схему, session secret и пароль со специальными символами, выбрав PostgreSQL без подключения.
- CLI `scripts.migrate_database --help` и `scripts.import_sqlite_to_postgres --help` успешно выполнены из распакованной поставки с выбранным файлом. Backend-сервер не запускался, БД не открывались.
- Изменённые Python-исходники разобраны грамматикой Python 3.9. `bash -n build-distribution.sh`, `git diff --check` и строгая валидация OpenSpec прошли.

Артефакты: `.tmp/settings-verification-72dmh9s2/result.json`, `build.log`, два файла CLI help, `distribution/`, `distribution.zip`, `unpacked/`. Исходник проверки — `.tmp/verify_settings_dotenv.py`. Временные файлы записаны UTF-8 без BOM.

## Ограничения и workflow

Корпоративный Docker-образ не собирался: Docker CLI отсутствует в окружении. Настоящие Vault Agent, Kubernetes и PostgreSQL не запускались; локальная проверка шаблона не является проверкой его выполнения Vault Agent. Приёмка других открытых изменений не изменялась. UI-прогон не требовался: frontend-логика и интерфейс не менялись.

`openspec validate load-configured-dotenv-file --strict` завершился успешно. Sync основных спецификаций и архивирование ожидают отдельных разрешений по AGENTS.md. Commit не создавался.
