## ADDED Requirements

### Requirement: Router сохраняет приоритет специфичных путей над catch-all

При переносе route-группы в `APIRouter` backend SHALL сохранять порядок разрешения специфичных paths и
перекрывающего их catch-all path.

#### Scenario: Запрос month route
- **WHEN** клиент вызывает `/api/freeze-days/month` или вложенный month path
- **THEN** запрос обрабатывает month handler, а не date catch-all handler

#### Scenario: Запрос date route
- **WHEN** клиент вызывает `/api/freeze-days/<date>` вне month paths
- **THEN** запрос обрабатывает date handler с прежним контрактом
