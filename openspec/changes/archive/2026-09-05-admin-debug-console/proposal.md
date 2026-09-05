## Why

Bootstrap-администратору нужен встроенный просмотр application log без доступа к файловой системе. Страница должна быть недоступна другим пользователям и вести себя как привычная потоковая консоль.

## What Changes

- Добавить страницу «Отладка» только для пользователя с `role=admin` и точным `login=admin`.
- Оставить на странице только Application log; не добавлять просмотр или редактирование БД и audit-журнал.
- Писать application и Uvicorn logs в ограниченный rotating UTF-8 `application.log` по относительному пути.
- Добавить фильтры уровня и текста, безопасное ограничение ответа и redaction секретов.
- Добавить console-like follow mode: начальная позиция внизу, слежение за новыми записями только пока пользователь находится внизу и кнопка «К последним» после ручной прокрутки вверх.
- Исключить access-записи polling endpoint `/api/debug/logs`, чтобы просмотр лога не создавал собственный шум.
- Выполнять текстовый поиск через существующий debounce-механизм, а не на каждый введённый символ.

## Capabilities

### New Capabilities

- `admin-debug-console`: безопасный admin-only просмотр application log.

### Modified Capabilities

Нет.

## Impact

Затрагиваются access control, FastAPI logging/router, React routing/navigation и UI страницы отладки. Новые таблицы БД и миграции не требуются.
