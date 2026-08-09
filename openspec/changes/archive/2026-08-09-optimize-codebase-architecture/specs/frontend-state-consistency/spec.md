## MODIFIED Requirements

### Requirement: Domain hooks владеют server-state orchestration

Queries и mutations Planning, Journal, Statistics и Settings SHALL размещаться в data/domain hooks, а page/modal components SHALL отвечать за presentation, form и selection state. Составные assignment mutations SHALL использовать согласованные bulk backend-контракты вместо orchestration нескольких одиночных HTTP-запросов в компонентах.

#### Scenario: Page загружает server data
- **WHEN** Journal или Statistics запрашивает данные
- **THEN** page использует domain hook вместо локального `useQuery` и ручного query function

#### Scenario: Task component изменяет данные
- **WHEN** Planning или task modal выполняет task mutation
- **THEN** component использует общий task mutation hook с централизованной invalidation и прежними callbacks/messages

#### Scenario: Assignment component выполняет составную операцию
- **WHEN** Planning или assignment modal сохраняет, переносит, автоназначает либо массово удаляет назначения
- **THEN** component использует assignment domain hook, а составная запись выполняется одним backend bulk endpoint
