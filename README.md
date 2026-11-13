# Планировщик команды поддержки

Веб-приложение для планирования задач и работы команд поддержки. Backend — FastAPI и SQLite, frontend — React и TypeScript. В production FastAPI обслуживает и API, и собранный интерфейс.

## Возможности

- Планирование задач и назначений по командам и датам; перенос и изменение статусов назначений.
- Шаблоны задач, сроки, блоки работ и зависимости с графом связей.
- Журнал работ и статистика с фильтрами.
- Уведомления о новых задачах и просроченных назначениях.
- Настройка команд, пользователей, ролей, рабочих справочников и дней заморозки.
- Светлая и тёмная темы; история изменений приложения доступна по версии в боковой панели.

Доступ разграничен ролями `user`, `editor` и `admin`.

## Запуск

Нужны Python 3.9+, Node.js и npm. Установите backend-зависимости и соберите frontend:

```bash
python -m venv .venv
python -m pip install -r requirements.txt
cd frontend
npm ci
npm run build
cd ..
python support_planner.py
```

Откройте <http://127.0.0.1:5093>. При первом запуске создаётся администратор `admin` с паролем `q12345678`; смените пароль после входа. Данные хранятся в `database.db` в рабочем каталоге.

Для production задайте постоянный `SESSION_SECRET_KEY`. Без него используется небезопасный ключ для локальной разработки.

## Разработка и проверки

Backend запускается командой `python support_planner.py`. Для frontend-разработки запустите backend, затем в каталоге `frontend` выполните `npm run dev`; Vite проксирует API и авторизацию на порт `5093`.

```bash
python -m unittest discover -s tests
cd frontend
npm test
npm run lint
npm run build
```

## Данные и дистрибутив

- `python -m scripts.migrate_database --database database.db` — миграция и проверка базы.
- `python -m scripts.seed_demo_data` — загрузка демо-данных. Перед изменением базы сохраните резервную копию.
- `./build-distribution.sh` — сборка автономного Linux-дистрибутива в `build/support-team-planner`.

В дистрибутиве `run.sh` запускает приложение, `check.sh` проверяет его состояние. `application_version.json` задаёт версию релиза, `changelog.json` — заметки к релизам; сборка генерирует `app_build_metadata.json` с ID билда.

## Контейнерный образ

Образ собирается из готового дистрибутива на базе `docker-dev.registry-ci.delta.mysecure_57117ba4eem0.ru/ubi8/python-312:latest`. Подготовка дистрибутива и Docker-сборка могут выполняться в разных job. Конфигурацию второй job предоставляет инфраструктура.

### Подготовка артефакта

В первой job нужны Python 3.9+, Node.js, npm и zip. Для установки полного набора frontend-зависимостей используйте Node.js 24. Из корня репозитория выполните:

```bash
npm --prefix frontend ci
./build-distribution.sh
```

Скрипт сам выполняет `npm run build`: дополнительно собирать frontend перед ним не требуется. Результат — каталог `build/support-team-planner` и архив `build/support-team-planner.zip`. Параметр `--output PATH` меняет каталог и путь архива на `PATH.zip`.

В архив входят Dockerfile, `.dockerignore`, backend, готовый `frontend/dist`, миграторы и метаданные сборки. Внешний каталог-обёртка внутри ZIP отсутствует. Docker и `pip.conf` для этого этапа не нужны; локальный `pip.conf` сборочный скрипт не читает и не включает в артефакт. Для ID из CI можно задать `BUILD_ID` при вызове скрипта; Docker-сборка сохранит полученный `app_build_metadata.json`.

### Сборка из архива

На машине с Docker и доступом к корпоративному registry распакуйте переданный архив в новый каталог:

```bash
mkdir image-context
unzip support-team-planner.zip -d image-context
```

Поместите свой `pip.conf` в `image-context/pip.conf`, затем выполните:

```bash
docker build -t support-team-planner:local image-context
```

Dockerfile копирует `pip.conf` в `/app/pip.conf` и использует `PIP_CONFIG_FILE=./pip.conf` при обновлении pip и установке `requirements.txt`. Этот файл остаётся в образе; его содержимое проект не создаёт и источник пакетов не подменяет. Node.js в образ не устанавливается. Отсутствие `pip.conf`, `frontend/dist/index.html` или `frontend/dist/taskTransitions.json` приводит к ошибке сборки.

### Запуск с внешним PostgreSQL

Образ использует `python support_planner.py`, рабочий каталог `/app`, порт `5093` и пользователя `1001:0`. Предоставьте запись в `/app` для создания и ротации `application.log`, а также в `/tmp` для временных TLS-файлов. Существующее файловое логирование сохраняется: `PYTHONUNBUFFERED=1` не перенаправляет эти логи в stdout. При замене контейнера его локальные логи теряются.

Для Kubernetes явно задайте `SUPPORT_PLANNER_DATABASE_URL` и постоянный `SESSION_SECRET_KEY` через окружение экземпляра; пароль PostgreSQL можно передать отдельно через `PGPASSWORD`. Схема задаётся `SUPPORT_PLANNER_DATABASE_SCHEMA`, по умолчанию `planner`; её заранее создаёт администратор БД. Если URL не задан, сохраняется SQLite-default приложения. Подключение, роли и TLS описаны в [POSTGRESQL.md](POSTGRESQL.md).

До первого запуска и после обновления схемы отдельно выполните мигратор из того же образа. Например, подготовьте вне контекста сборки закрытые файлы окружения `/secure/planner-migration.env` и `/secure/planner-runtime.env`: первый содержит подключение migration-роли, второй — runtime-роли и `SESSION_SECRET_KEY`. Значение `SUPPORT_PLANNER_DATABASE_SCHEMA` должно совпадать в обоих файлах и при импорте SQLite. Значение по умолчанию задаётся приложением и одинаково для контейнера и локального запуска.

```bash
docker run --rm --env-file /secure/planner-migration.env \
  support-team-planner:local python -m scripts.migrate_database --postgresql

docker run --rm --name support-team-planner \
  --env-file /secure/planner-runtime.env -p 5093:5093 \
  support-team-planner:local
```

Если PostgreSQL требует файл CA или клиентские сертификаты, смонтируйте их в оба контейнера с правом чтения для UID 1001 и укажите соответствующие пути через параметры libpq, например `PGSSLROOTCERT`. Адрес PostgreSQL должен быть доступен из контейнера; `localhost` внутри него относится к самому контейнеру.

При обычном HTTP-запуске интерфейс доступен на `http://127.0.0.1:5093`. Существующий режим TLS через Vault сохраняется при соответствующей настройке окружения. Docker-сборка и стандартная команда запуска не применяют PostgreSQL-миграции автоматически; при неподготовленной схеме startup завершается с ошибкой.

### Vault Agent Injector (KV v1)

Приложение и CLI читают один UTF-8 dotenv-файл по пути `SUPPORT_PLANNER_ENV_FILE`, заданному в окружении до запуска Python. Файл содержит строки `KEY=value`; `export` не требуется. Окружение процесса имеет приоритет, а `${...}` в выбранном файле сохраняется буквально. Явный путь заменяет автоматический поиск `.env`. Ошибка чтения, включая пустой путь и некорректный UTF-8, останавливает запуск. Без переменной сохраняется обычный поиск `.env`; `SUPPORT_PLANNER_SKIP_DOTENV=1` отключает оба режима.

Пример фрагмента Deployment для KV v1. Замените Vault-роль, service account, образ и путь секрета на свои. Пример предполагает, что секрет содержит четыре одноимённых поля: URL включает пользователя и БД, пароль хранится как `PGPASSWORD`. TLS-параметры подключения задаются в соответствии с PostgreSQL.

```yaml
spec:
  template:
    metadata:
      annotations:
        vault.hashicorp.com/agent-inject: "true"
        vault.hashicorp.com/role: "planner-runtime"
        vault.hashicorp.com/agent-inject-secret-env: "secret/planner/env"
        vault.hashicorp.com/agent-inject-file-env: "env"
        vault.hashicorp.com/secret-volume-path-env: "/config/secret/planner-env"
        vault.hashicorp.com/agent-inject-template-env: |
          {{- with secret "secret/planner/env" -}}
          SUPPORT_PLANNER_DATABASE_URL='{{ .Data.SUPPORT_PLANNER_DATABASE_URL | replaceAll "\\" "\\\\" | replaceAll "'" "\\'" }}'
          SUPPORT_PLANNER_DATABASE_SCHEMA='{{ .Data.SUPPORT_PLANNER_DATABASE_SCHEMA | replaceAll "\\" "\\\\" | replaceAll "'" "\\'" }}'
          SESSION_SECRET_KEY='{{ .Data.SESSION_SECRET_KEY | replaceAll "\\" "\\\\" | replaceAll "'" "\\'" }}'
          PGPASSWORD='{{ .Data.PGPASSWORD | replaceAll "\\" "\\\\" | replaceAll "'" "\\'" }}'
          {{- end }}
    spec:
      serviceAccountName: planner
      containers:
        - name: planner
          image: support-team-planner:local
          env:
            - name: SUPPORT_PLANNER_ENV_FILE
              value: "/config/secret/planner-env/env"
```

Vault монтирует каталог `/config/secret/planner-env` и создаёт в нём файл `env`. KV v1 использует `.Data.<ключ>` и путь без служебного `/data/`. Фильтры `replaceAll` экранируют обратную косую черту и одинарную кавычку для dotenv. Если пароль хранится в другом секрете, получите его отдельным блоком `with secret` в том же шаблоне и запишите как `PGPASSWORD` в этот файл.

Сохраняйте стандартную предварительную подготовку файла Vault Agent init-контейнером (`agent-pre-populate=true`) и доступ на чтение для пользователя приложения `1001:0`. Не монтируйте каталог секретов поверх `/app`, где находится код. Семантика путей описана в [аннотациях HashiCorp](https://developer.hashicorp.com/vault/docs/deploy/kubernetes/injector/annotations).

Обычный Deployment использует стандартную команду образа. Для отдельной migration Job задайте её Vault-роль, файл с migration-реквизитами и тот же параметр схемы, затем укажите:

```yaml
args: ["python", "-m", "scripts.migrate_database", "--postgresql"]
```

Приложение и CLI используют общий загрузчик `backend/settings.py`. После обновления файла перезапустите процесс: dotenv читается при запуске. Секреты подключаются во время работы контейнера и не упаковываются в дистрибутив или образ. Запись пути только в самом dotenv-файле не выбирает этот файл: `SUPPORT_PLANNER_ENV_FILE` задаётся внешним окружением до запуска.

## Структура

- `backend/` — приложение FastAPI, бизнес-логика, доступ к SQLite (`db/`) и API-маршруты (`routers/`).
- `frontend/` — React-интерфейс и его тесты.
- `scripts/` — миграции и генераторы данных.
- `tests/` — backend- и сквозные тесты.
- `support_planner.py` — корневая точка запуска; `build-distribution.sh` — production-сборка.

## PostgreSQL 15

SQLite остаётся вариантом по умолчанию. Для PostgreSQL задайте `SUPPORT_PLANNER_DATABASE_URL` и при необходимости `SUPPORT_PLANNER_DATABASE_SCHEMA` (по умолчанию `planner`). Администратор заранее создаёт схему, затем выполняется `python -m scripts.migrate_database --postgresql` и запускается приложение. Для переноса из SQLite используйте подготовку `--schema-only` и импорт с тем же параметром схемы. Зависимость Psycopg ограничена веткой 3.2 для Python 3.9. Полная инструкция по runtime/migration-ролям, двум независимым экземплярам, первичному переносу, `--replace-target`, тестовой матрице, backup/restore и финальному переключению: [POSTGRESQL.md](POSTGRESQL.md).
