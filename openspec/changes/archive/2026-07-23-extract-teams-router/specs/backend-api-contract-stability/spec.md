## ADDED Requirements

### Requirement: Router сохраняет entity access и составную транзакцию

Перемещение entity handlers в `APIRouter` SHALL сохранять request-derived authorization checks и границы
существующих composite transactions.

#### Scenario: Доступ к команде после переноса
- **WHEN** пользователь запрашивает команду или вложенный team resource
- **THEN** router применяет прежние user/role и team-access правила

#### Scenario: Создание команды после переноса
- **WHEN** создание команды или выдача доступа завершается ошибкой
- **THEN** обе записи откатываются в прежней composite transaction

#### Scenario: Вложенные team paths
- **WHEN** клиент вызывает blocks или assignees path команды
- **THEN** запрос попадает в прежний handler и сохраняет контракт
