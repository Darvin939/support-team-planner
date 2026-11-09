## MODIFIED Requirements

### Requirement: Data access разделён по доменным границам
Backend SHALL размещать DAO-функции в доменных модулях, сохраняя единый connection/transaction layer и наблюдаемое поведение существующих роутеров. Поддержка SQLite и PostgreSQL SHALL использовать общую публичную границу DAO; драйверные различия SHALL оставаться внутри инфраструктуры хранения.

#### Scenario: DAO-группа перенесена
- **WHEN** функции одного домена извлекаются из монолитного модуля
- **THEN** существующие API-контракты, транзакции и тестовые сценарии остаются неизменными

#### Scenario: Роутер использует data access
- **WHEN** endpoint вызывает DAO-функцию
- **THEN** соединение текущего HTTP-запроса переиспользуется по существующей модели lifecycle

#### Scenario: DAO проектируется для будущего backend
- **WHEN** доменный DAO выделяется или адаптируется к другой СУБД
- **THEN** его публичная граница не зависит от SQLite-specific или PostgreSQL-specific connection/cursor API, а диалектные операции остаются внутри database backend abstraction

#### Scenario: PostgreSQL ещё не подключается
- **WHEN** экземпляр запущен в режиме SQLite без PostgreSQL URL
- **THEN** он не открывает PostgreSQL-соединений, не применяет PostgreSQL-миграции и не требует PostgreSQL-сервера для работы

#### Scenario: PostgreSQL подключён как рабочий backend
- **WHEN** экземпляр настроен на PostgreSQL
- **THEN** его адаптер, конфигурация и миграции реально используются через общую границу DAO и проверяются вместе с SQLite
