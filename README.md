# Планировщик команды поддержки

Веб-приложение для планирования работ команд поддержки: ведения задач и назначений, контроля сроков и зависимостей, просмотра журнала и статистики, а также управления пользователями и справочниками.

Backend написан на FastAPI и хранит данные в SQLite. Пользовательский интерфейс — одностраничное React-приложение; в production его собранные файлы раздаёт тот же FastAPI-сервер.

## Возможности

- планирование задач по командам и датам;
- создание назначений и изменение их статусов;
- зависимости между задачами и визуализация графа;
- журнал работ, фильтры и статистика;
- уведомления о новых задачах и просроченных назначениях;
- управление командами, пользователями, блоками и днями заморозки;
- разграничение доступа по ролям `user`, `editor` и `admin`;
- светлая и тёмная темы интерфейса.

## Технологии

- Python, FastAPI, Uvicorn;
- SQLite;
- React, TypeScript, Vite;
- Ant Design, TanStack Query, React Router;
- стандартный модуль `unittest` для backend-тестов;
- Vitest и React Testing Library для frontend-тестов.

## Требования

- Python 3;
- Node.js и npm;
- Bash — только для вспомогательных скриптов `run.sh`, `check.sh` и `build-distribution.sh`.

## Быстрый запуск

Установите зависимости backend:

```bash
python -m venv .venv
```

Активируйте окружение в PowerShell:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Или в Bash:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Установите зависимости и соберите frontend:

```bash
cd frontend
npm ci
npm run build
cd ..
```

Запустите приложение из корня репозитория:

```bash
python support_planner.py
```

Откройте <http://127.0.0.1:5093>. При первом запуске миграции SQLite создадут защищённую учётную запись администратора:

- логин: `admin`;
- пароль: `q12345678`.

После первого входа смените пароль в интерфейсе.

> Backend раздаёт файлы из `frontend/dist`. После изменения frontend выполните `npm run build` заново.

## Разработка

Для разработки backend запустите из корня проекта:

```bash
python support_planner.py
```

Для разработки frontend во втором терминале:

```bash
cd frontend
npm run dev
```

Vite проксирует запросы `/api`, `/login` и `/logout` на `http://localhost:5093`, поэтому frontend и backend работают с общей сессионной авторизацией. Подробности о структуре и командах frontend приведены в [frontend/README.md](frontend/README.md).

## Настройка

Приложение слушает `0.0.0.0:5093`. Основная база данных находится в файле `database.db` в рабочем каталоге.

Для production обязательно задайте постоянный секрет сессий:

```powershell
$env:SESSION_SECRET_KEY = "длинное-случайное-значение"
python support_planner.py
```

Без `SESSION_SECRET_KEY` приложение запускается с небезопасным ключом для локальной разработки и выводит предупреждение.

HTTPS может быть настроен через HashiCorp Vault. Поддерживаются переменные окружения `VAULT_TENANT`, `VAULT_ADDR`, `VAULT_KV_PATH`, `ROLE_ID` и `SECRET_ID`; они также могут быть заданы в `.env`. Если сертификат и ключ не получены, сервер запускается по HTTP.

## Демо-данные

Чтобы наполнить базу небольшим воспроизводимым набором данных:

```bash
python seed_demo_data.py
```

Для нагрузочного набора предназначен отдельный генератор. Перед запуском изучите его параметры — значения по умолчанию создают миллионы записей:

```bash
python seed_large_demo_data.py --help
```

Скрипты изменяют `database.db`. Перед их запуском сохраните резервную копию базы.

## Проверки

Backend-тесты:

```bash
python -m unittest discover -s tests
```

Frontend-тесты, линтер и production-сборка:

```bash
cd frontend
npm test
npm run lint
npm run build
```

## Production-сборка

Скрипт собирает frontend и формирует автономный каталог Linux-приложения:

```bash
./build-distribution.sh
```

По умолчанию результат создаётся в `build/support-team-planner`. Другой каталог можно указать явно:

```bash
./build-distribution.sh --output /path/to/support-team-planner
```

В готовом каталоге `run.sh` запускает приложение, а `check.sh` запускает его в фоне, если процесс ещё не работает, и пишет вывод в `support-team-planner.log`.

## Структура проекта

```text
.
├── support_planner.py       # FastAPI-приложение и запуск Uvicorn
├── routers/                 # HTTP- и API-маршруты
├── db/                      # доступ к SQLite, схема и миграции
├── frontend/                # React-приложение
├── tests/                   # backend-тесты
├── openspec/                # спецификации и история изменений
├── seed_demo_data.py        # небольшой демонстрационный набор
├── seed_large_demo_data.py  # генератор нагрузочных данных
└── database.db              # рабочая база SQLite
```
