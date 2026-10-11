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

## Структура

- `backend/` — приложение FastAPI, бизнес-логика, доступ к SQLite (`db/`) и API-маршруты (`routers/`).
- `frontend/` — React-интерфейс и его тесты.
- `scripts/` — миграции и генераторы данных.
- `tests/` — backend- и сквозные тесты.
- `support_planner.py` — корневая точка запуска; `build-distribution.sh` — production-сборка.
