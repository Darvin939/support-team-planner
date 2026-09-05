# admin-debug-console Specification

## Purpose

Безопасный просмотр application log, доступный только bootstrap-администратору.

## Requirements

### Requirement: Строго ограниченный доступ к странице отладки
Backend SHALL разрешать debug route и log endpoint только аутентифицированному пользователю с `role = admin` и точным `login = admin`. Frontend SHALL показывать bug-пункт навигации только этому пользователю.

#### Scenario: Bootstrap admin открывает страницу
- **WHEN** пользователь с `role=admin`, `login=admin` запрашивает debug route
- **THEN** страница и log API доступны

#### Scenario: Другой пользователь отклонён
- **WHEN** неавторизованный пользователь или пользователь с другим login запрашивает debug route или API
- **THEN** backend отвечает `401` или `403` согласно состоянию авторизации

### Requirement: Безопасный application log
The system SHALL write application and Uvicorn records to one relative rotating UTF-8 `application.log` and SHALL expose a bootstrap-admin-only endpoint with bounded output, text/level filters and secret redaction. The endpoint MUST NOT accept a file path.

#### Scenario: Фильтрация уровня
- **WHEN** admin выбирает уровень `ERROR`
- **THEN** API и UI показывают только записи уровня `ERROR`

#### Scenario: Секрет в сообщении
- **WHEN** запись содержит password, cookie, token или secret
- **THEN** значение маскируется до записи либо перед выдачей API

#### Scenario: Uvicorn пишет запись
- **WHEN** Uvicorn или application logger создаёт запись
- **THEN** запись появляется в том же относительном файле, который читает debug API

### Requirement: Следящий просмотр лога
The UI SHALL initially scroll to the newest record, follow appended records while the user remains at the bottom, preserve manual position after scrolling upward, and show a jump-to-end control when not at the bottom.

#### Scenario: Новые записи в режиме follow
- **WHEN** пользователь находится внизу и появляются новые записи
- **THEN** viewport остаётся у последних записей

#### Scenario: Пользователь просматривает историю
- **WHEN** пользователь прокрутил вверх и появляются новые записи
- **THEN** позиция сохраняется и показывается кнопка «К последним»

### Requirement: Лог не записывает собственный polling
The application log SHALL exclude Uvicorn access records for `/api/debug/logs` polling while preserving errors and all other records.

#### Scenario: UI обновляет лог
- **WHEN** frontend выполняет периодический GET `/api/debug/logs`
- **THEN** соответствующая access-запись не добавляется в `application.log`

### Requirement: Отложенный текстовый поиск
The log search field SHALL use the application's existing debounced-value mechanism so typing does not issue a request for every character.

#### Scenario: Пользователь вводит поисковую строку
- **WHEN** значение поиска быстро изменяется несколько раз
- **THEN** API-запрос выполняется после debounce-задержки с последним значением

### Requirement: Отсутствие функций БД и аудита
The debug page and API SHALL NOT expose SQLite browsing/editing or an audit journal, and the change SHALL NOT create a debug audit table or migration.

#### Scenario: Страница отладки открыта
- **WHEN** bootstrap admin открывает страницу
- **THEN** на ней присутствует только Application log без вкладок SQLite и Audit
