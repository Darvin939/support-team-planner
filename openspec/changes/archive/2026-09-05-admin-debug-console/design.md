## Context

Приложение использует FastAPI, Uvicorn, React и Ant Design. Нужен минимальный встроенный просмотр application log только для bootstrap-admin. Функции просмотра/редактирования SQLite и audit исключены из изменения.

## Goals / Non-Goals

**Goals:**

- Доступ к странице и API только для `role=admin`, `login=admin`.
- Относительный rotating UTF-8 файл `application.log`, общий для writer и reader.
- Структурированные записи с временем, уровнем, logger и сообщением.
- Фильтры уровня и текста, redaction секретов и ограничение размера ответа.
- Потоковое обновление с корректным сохранением позиции прокрутки.

**Non-Goals:**

- Просмотр или редактирование SQLite.
- Произвольный SQL.
- Audit-таблица, audit API и восстановление изменений.
- Доступ других администраторов с login, отличным от `admin`.

## Decisions

1. Backend dependency проверяет действующую session, `role == 'admin'` и `login == 'admin'`; скрытие пункта меню является дополнительным UX-ограничением.
2. Writer и endpoint используют один относительный `application.log`. Один `RotatingFileHandler` подключается к application/Uvicorn logger без дубликатов; Uvicorn не перезаписывает конфигурацию.
3. Endpoint не принимает путь к файлу, ограничивает число строк, фильтрует level/search и повторно маскирует секреты перед выдачей.
4. UI содержит только панель лога. Она стартует внизу, продолжает следовать за новыми строками только пока пользователь остаётся у нижней границы и иначе показывает «К последним».
5. Навигация использует bug icon.
6. Logging filter отбрасывает только Uvicorn access-records запросов `/api/debug/logs`; ошибки endpoint и записи других logger сохраняются.
7. Текстовый фильтр UI использует существующий `useDebouncedValue` с задержкой 500 мс; level-фильтр применяется сразу.

## Risks / Trade-offs

- Секреты в логах → redaction до записи и перед API-ответом.
- Рост файла → ограниченный размер и число rotation-файлов.
- Сброс ручной позиции → явное состояние follow-mode и порог нижней границы.
- Потеря Uvicorn записей из-за повторной конфигурации → отключение стандартного `log_config` Uvicorn и единый handler.

## Migration Plan

Миграция БД не требуется. Добавляются logging configuration, admin-only endpoint, SPA route и UI.

## Open Questions

Нет.
