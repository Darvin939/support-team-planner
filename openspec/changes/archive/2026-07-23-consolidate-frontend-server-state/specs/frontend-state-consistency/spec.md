## MODIFIED Requirements

### Requirement: Изменения данных инвалидируют согласованный cache
Система SHALL использовать исключительно централизованные типизированные query keys и доменные invalidation policies и SHALL обновлять все зависимые представления после изменения задач, назначений, зависимостей и настроек.

#### Scenario: Изменено назначение
- **WHEN** назначение создано, изменено, перенесено или удалено
- **THEN** cache назначений и активных назначений инвалидируется, а cache задач инвалидируется для операций, влияющих на состояние задач

#### Scenario: Изменена задача
- **WHEN** задача создана, изменена, восстановлена, удалена, переупорядочена либо меняет статус или приоритет
- **THEN** единая task policy инвалидирует все затронутые task lists/details и связанные представления

#### Scenario: Изменена зависимость
- **WHEN** зависимость задачи добавлена или удалена
- **THEN** cache списка зависимостей и графа инвалидируется

#### Scenario: Изменена настройка
- **WHEN** команда, пользователь, сегмент, блок, шаблон или freeze day создан, изменён либо удалён
- **THEN** mutation использует канонический query-key root соответствующей settings entity

#### Scenario: Cache key формируется frontend-кодом
- **WHEN** query или mutation обращается к React Query cache
- **THEN** код использует registry `queryKeys`, а не локальный строковый массив

### Requirement: Пагинация сохраняет текущее поведение
Система SHALL предоставлять общий механизм page/offset/pageSize для Planning, Journal, Statistics, Settings, history и task archive, сохраняя текущие размеры страниц, сбросы и варианты отображения каждого экрана.

#### Scenario: Изменён размер страницы
- **WHEN** пользователь выбирает новый размер страницы
- **THEN** соответствующий список сбрасывается на первую страницу и запрашивает новые границы

#### Scenario: Изменены фильтры
- **WHEN** фильтр экрана изменяет набор результатов
- **THEN** пагинация сбрасывается в соответствии с текущим поведением этого экрана

#### Scenario: Offset pagination архива или истории
- **WHEN** пользователь переходит между страницами task archive, journal или history
- **THEN** общий pagination state вычисляет прежний offset и сохраняет прежний размер страницы

## ADDED Requirements

### Requirement: Server query использует канонический URL builder

Frontend SHALL формировать query parameters HTTP GET-запросов через общий URL builder с едиными правилами пропуска пустых значений и сохранения значимых `0`/`false`.

#### Scenario: Запрос с заполненными фильтрами
- **WHEN** data hook формирует запрос с пагинацией, поиском, датами или наборами идентификаторов
- **THEN** builder кодирует параметры и создаёт тот же backend URL contract

#### Scenario: Пустой необязательный фильтр
- **WHEN** параметр равен `null`, `undefined` или пустой строке
- **THEN** builder не включает его в query string

#### Scenario: Значимые false и zero
- **WHEN** параметр равен `false` или `0`
- **THEN** builder сохраняет его в query string

### Requirement: Domain hooks владеют server-state orchestration

Queries и mutations Planning, Journal, Statistics и Settings SHALL размещаться в data/domain hooks, а page/modal components SHALL отвечать за presentation, form и selection state.

#### Scenario: Page загружает server data
- **WHEN** Journal или Statistics запрашивает данные
- **THEN** page использует domain hook вместо локального `useQuery` и ручного query function

#### Scenario: Task component изменяет данные
- **WHEN** Planning или task modal выполняет task mutation
- **THEN** component использует общий task mutation hook с централизованной invalidation и прежними callbacks/messages
