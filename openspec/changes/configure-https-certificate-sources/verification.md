# Проверка реализации

Дата: 2026-11-13. Окружение: macOS, Python 3.9.25.

## Результат

Реализован порядок «смонтированные файлы → прежний Vault AppRole → HTTP на 5093». Найденная некорректная смонтированная пара завершает запуск. Оба действующих варианта main сохранены, добавлен журнал выбранного протокола. Смонтированные файлы не копируются; временные файлы резервного способа сохраняют очистку через atexit. Ошибки не печатают тело ответа Vault или секреты.

Изменены только TLS-модуль, сообщения запуска, `.env.example`, README, тесты и артефакты этого изменения. Dockerfile, команда запуска, build-distribution.sh, frontend, dev-прокси, общий UI-harness и AGENTS.md не изменялись.

## Backend

```bash
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 SUPPORT_PLANNER_SKIP_DOTENV=1 SUPPORT_PLANNER_TEST_BACKEND=sqlite \
  .venv/bin/python -m pytest -q tests/test_ssl_context.py tests/test_settings.py \
  tests/test_debug_console.py tests/test_api_error_format.py \
  tests/test_storage_configuration.py tests/test_postgresql_schema.py
```

**99 passed**, 12.09 s. Из них 25 новых TLS-проверок: приоритет файлов, отсутствие Vault и копирования при рабочей паре, загрузка путей из внешнего dotenv, отсутствие/неполнота/пустые пути, отсутствующие файлы, каталог, ошибки доступа, некорректный PEM, несовпадающий и зашифрованный ключ, совместимость запросов AppRole и полей секрета, HTTP после ошибки резервного способа, очистка временного каталога, безопасная диагностика и аргументы запуска HTTPS/HTTP. Проверка ключа с паролем выполняется в дочернем процессе с закрытым stdin и таймаутом: интерактивного запроса нет.

README-фрагменты разобраны YAML-парсером: пути приложения совпадают с каталогом и именем файлов Agent, шаблоны используют KV v1 `.Data`, права указаны строкой `0400`. Семантика аннотаций сверена с [документацией HashiCorp](https://developer.hashicorp.com/vault/docs/deploy/kubernetes/injector/annotations).

## Настоящий запуск HTTPS и HTTP

```bash
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 SUPPORT_PLANNER_SKIP_DOTENV=1 \
  SUPPORT_PLANNER_UI_BROWSER_CHANNEL=chrome PYTHONPATH=. \
  .venv/bin/python tests/tls_startup_smoke.py
```

Успешный прогон: [.tmp/tls-startup-af72dc411fc0/result.json](../../../.tmp/tls-startup-af72dc411fc0/result.json).

- Перед проверкой собран свежий production-frontend, Vite/dev-server не запускался.
- HTTPS запущен через `python support_planner.py` с путями из отдельного dotenv и сгенерированной двухдневной loopback PEM-парой. Рабочие сертификаты и Vault не использовались.
- Отдельный SSL-клиент доверяет тестовому сертификату, проверяет его SAN, точное DER-содержимое и TLS-handshake; согласован TLSv1.3. Обычный HTTP на HTTPS-listener отклоняется.
- И для HTTPS, и для HTTP выполнен настоящий вход `admin` через форму production-интерфейса, получена `sp_session`, отрисована защищённая страница «Планирование», `/api/me` вернул администратора. Ошибок JavaScript нет.
- HTTP проверен без настроенной TLS-пары и без Vault-реквизитов: запрос к рабочему Vault невозможен. В журнале подтверждены резервный путь и выбор HTTP.
- Каждый режим использовал собственную SQLite БД в каталоге артефактов. До запуска создан уникальный backup через SQLite API; после остановки созданного процесса выполнены restore, checkpoint, quick_check и сравнение содержимого. Backup и результаты сохранены. Рабочая БД не изменялась.
- Созданные backend-процессы остановлены и дождались завершения; Playwright/browser закрыты в finally.

Первый запуск не нашёл отдельный Chromium headless shell для установленного Playwright. После этой фактической ошибки использован уже установленный Google Chrome через поддерживаемый параметр канала; установка браузеров не выполнялась. Первый каталог: `.tmp/tls-startup-651c9f9ddeec`; backend в нём не запускался.

## Дистрибутив и совместимость

```bash
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 SUPPORT_PLANNER_SKIP_DOTENV=1 \
  .venv/bin/python .tmp/verify_tls_distribution.py
```

Результат: [.tmp/tls-distribution-x6o2h9sr/result.json](../../../.tmp/tls-distribution-x6o2h9sr/result.json).

Свежий `build-distribution.sh` повторно собрал production-frontend и создал каталог/ZIP с 96 одинаковыми файлами. TLS-модуль, application, settings и README совпадают с текущими исходниками. Сертификаты, ключи, тестовые fixtures, `.env`, БД, логи и тестовые сценарии не включены. Стандартный Docker CMD сохранён. Упакованный TLS-модуль отдельно проверен для смонтированной пары и отсутствия пары с возвратом HTTP-пути. Весь новый/изменённый Python-код исполнялся под 3.9.25 и дополнительно разобран AST с грамматикой 3.9.

## Ограничения и следующие этапы

- Прямые Vault-запросы проверены mock-контрактами. Реальный Vault, Kubernetes Injector и корпоративный контейнер не запускались; UID и доступы в целевом Deployment требуют проверки при развёртывании.
- PostgreSQL и полная storage UI-матрица в этом изменении не запускались: код хранилища и frontend не менялись. Этот результат не закрывает PostgreSQL-приёмку других изменений.
- Sync основных спецификаций, архивирование, commit и развёртывание не выполнялись. Для следующих этапов требуется отдельное разрешение по AGENTS.md.

Итоговые `openspec validate configure-https-certificate-sources --strict` и `git diff --check` выполнены успешно.
