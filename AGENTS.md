# Инструкции для агентов

## Рабочий процесс OpenSpec

- Все задачи по умолчанию выполнять через OpenSpec: подготовить или обновить артефакты изменения, реализовать задачи, синхронизировать основные спецификации и архивировать завершённое изменение.
- Перед каждым этапом OpenSpec, кроме explore и propose (archive, sync, и т.д.), а так же перед созданием commit спрашивать разрешение.
- Отклоняться от OpenSpec только по явному указанию пользователя либо для простой мета-настройки рабочего процесса, не затрагивающей поведение проекта.

## Тестирование UI

- UI-тесты проводить только с использованием Python + Playwright.
- Считать, что Python, пакет `playwright` и Chromium уже установлены и доступны. Не проверять их наличие и не переустанавливать перед каждым тестом; диагностировать окружение только после фактической ошибки запуска.
- Сохранять исходники, временные Python-сценарии, JSON, логи и текстовые fixtures в UTF-8 без BOM. Для Python задавать `PYTHONUTF8=1` и `PYTHONIOENCODING=utf-8` в окружении дочернего процесса.

### Подготовка и запуск

1. Перед тестом создать WAL-безопасную резервную копию `database.db` через SQLite backup API с уникальным именем. Простого `Copy-Item database.db` недостаточно: актуальные изменения могут находиться в `database.db-wal`. Не перезаписывать существующие копии:

   ```powershell
   $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
   $backup = "database.db.ui-test-$stamp.bak"
   @'
   import sqlite3
   source = sqlite3.connect("database.db")
   target = sqlite3.connect(r"BACKUP_PATH")
   with target:
       source.backup(target)
   target.close()
   source.close()
   '@.Replace('BACKUP_PATH', $backup) | python -
   ```

2. После завершения всех изменений frontend и непосредственно перед UI-тестом собрать production-frontend. Ранее собранный `frontend/dist` не использовать: backend раздаёт именно его, поэтому тест иначе проверит устаревший UI. Команду запускать из `frontend`:

   ```powershell
   npm run build
   ```

3. Не запускать Vite/dev-server. Для UI-теста запускать production-backend командой `python support_planner.py`; он обслуживает собранный frontend на `http://127.0.0.1:5093`. Для локального HTTP-запуска не требуются обязательные переменные окружения; не проверять их перед каждым запуском.
4. Если тест изменял БД, после теста вернуть backup в `database.db` также через SQLite backup API, а затем выполнить `PRAGMA wal_checkpoint(TRUNCATE)`. Перед восстановлением обязательно остановить backend, чтобы SQLite-соединения были закрыты. Не восстанавливать БД обычным копированием поверх файла: существующий WAL может повторно применить тестовые изменения. Не удалять backup до успешной проверки восстановленной БД.

### Базовый шаблон Playwright

Для каждого UI-теста адаптировать следующий шаблон. Он запускает backend как дочерний Python-процесс, ждёт готовности `5093` и гарантированно останавливает запущенный им backend в `finally`:

```python
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parent
env = os.environ.copy()
env["PYTHONUTF8"] = "1"
env["PYTHONIOENCODING"] = "utf-8"

backend = subprocess.Popen(
    [sys.executable, "support_planner.py"],
    cwd=ROOT,
    env=env,
    # Не использовать PIPE без постоянного чтения: буфер логов Uvicorn заполнится и
    # заблокирует backend. Для обычного теста достаточно DEVNULL; при диагностике
    # направлять вывод в открытый UTF-8 log-файл и закрывать его в finally.
    stdout=subprocess.DEVNULL,
    stderr=subprocess.STDOUT,
)

try:
    for _ in range(40):
        if backend.poll() is not None:
            raise RuntimeError("Backend stopped before startup")
        try:
            with urllib.request.urlopen("http://127.0.0.1:5093/login", timeout=1) as response:
                if response.status == 200:
                    break
        except Exception:
            time.sleep(0.25)
    else:
        raise RuntimeError("Backend did not become ready on port 5093")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(viewport={"width": 1440, "height": 1000})
            page = context.new_page()
            page.goto("http://127.0.0.1:5093/login")

            page.locator("form input").nth(0).fill("admin")
            page.locator("form input").nth(1).fill("q12345678")
            page.locator("form button[type='submit']").click()
            page.wait_for_url("**/planning**")

            # Arrange / Act / Assert конкретного UI-сценария.
        finally:
            browser.close()
finally:
    backend.terminate()
    try:
        backend.wait(timeout=5)
    except subprocess.TimeoutExpired:
        backend.kill()
        backend.wait(timeout=5)
```

### Авторизация в UI-тестах

- Не мокать `/login`, `/api/me` и protected document-маршруты. UI-тест должен авторизоваться через реальную форму в production-backend и получать настоящую session cookie.
- По умолчанию входить под администратором: логин `admin`, пароль `q12345678`.
- Если сценарий проверяет ограничения роли и БД наполнена `seed_demo_data.py`, использовать учётные записи из demo-данных: редактор `ivanov` / `password123`, пользователь `petrova` / `password123`.
- Не понижать роль bootstrap-администратора ради теста. Если для нужной роли нет заранее заданной учётной записи, создать её под администратором как часть Arrange и после теста восстановить БД из backup.
- После submit формы ждать не только URL, но и устойчивый целевой DOM-элемент защищённой страницы (например, пункт навигации). Не использовать таблицу как общий признак готовности: при пустых данных страница может корректно отображать `Empty` без `<table>`.
- Ant Design может оставлять в DOM скрытые дубли dropdown/menu/modal. Для интеракций с ними ограничивать локатор видимым элементом, например `.ant-dropdown-menu-item:visible`.
- В `page.request` передавать абсолютный URL (`http://127.0.0.1:5093/api/...`): в отличие от браузерной навигации, API request context страницы не всегда разрешает относительные URL.
- После входа переходить между SPA-разделами через видимую навигацию приложения и ждать одновременно целевой URL и характерный для раздела DOM-элемент. Само изменение URL ещё не доказывает, что ленивый маршрут уже отрисовался.

- После любого тестирования обязательно останавливать все Python-процессы, запущенные агентом для этого теста, чтобы они не оставались работать в фоне.
- Не останавливать Python-процессы, которые агент не запускал в рамках текущего тестирования.
