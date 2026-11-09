## RENAMED Requirements

- FROM: `### Requirement: One SQLite connection per HTTP request`
- TO: `### Requirement: One database connection per HTTP request`

## MODIFIED Requirements

### Requirement: One database connection per HTTP request
Приложение SHALL открывать не более одного соединения выбранной СУБД на HTTP-запрос, кроме `/react-assets/`, переиспользовать его во всех DAO-вызовах запроса и закрывать после обработки независимо от исхода. Перед закрытием незавершённая транзакция SHALL откатываться. Сетевое открытие и закрытие PostgreSQL-соединения SHALL NOT блокировать event loop.

#### Scenario: Multiple DAO calls in one request share a connection
- **WHEN** обработчик вызывает несколько DAO, например список задач и его total
- **THEN** все вызовы используют одно открытое для запроса соединение SQLite либо PostgreSQL

#### Scenario: require_login's own DB call is included
- **WHEN** проверка авторизации выполняет обращение к БД
- **THEN** используется то же соединение, что и в последующих DAO обработчика

#### Scenario: Connection is closed after the response, even on error
- **WHEN** обработчик завершается необработанной ошибкой
- **THEN** незавершённая транзакция откатывается, соединение закрывается и не остаётся удерживаемой блокировки

#### Scenario: Non-request call sites are unaffected
- **WHEN** DAO вызывается вне HTTP-запроса и вне явной общей транзакции
- **THEN** вызов самостоятельно открывает и закрывает своё соединение, а подготовка схемы выполняется по правилам выбранной СУБД

#### Scenario: Static asset requests don't open a connection
- **WHEN** путь запроса начинается с `/react-assets/`
- **THEN** request-scoped соединение не открывается

#### Scenario: The shared connection works across the event-loop and worker threads
- **WHEN** соединение последовательно используется инфраструктурой запроса и синхронным обработчиком
- **THEN** смена потока не вызывает ошибку драйвера, а одновременное использование одного соединения разными потоками не допускается

#### Scenario: A failed DAO call doesn't poison a later call in the same request
- **WHEN** самостоятельный DAO-вызов вне составной транзакции подавляет ожидаемую DB-ошибку и следующий вызов того же запроса сохраняет данные
- **THEN** работа первого вызова откатывается до возврата, PostgreSQL не остаётся в aborted transaction, а следующий commit не сохраняет частичные изменения первого вызова

#### Scenario: Исключение преобразовано в доменное
- **WHEN** DAO преобразовал ошибку драйвера в доменное исключение
- **THEN** транзакционная граница откатывает операцию независимо от класса вышедшего исключения

#### Scenario: Запрос выполнял только чтение
- **WHEN** обработка запроса завершается после SELECT
- **THEN** соединение закрывается с завершённой транзакцией и не остаётся idle in transaction
