## ADDED Requirements

### Requirement: РћР±С‰РёР№ layout РґР»СЏ РґР°С‚РѕРІС‹С… С‚Р°Р±Р»РёС†
The auto-scheduling grid and assignment timeline SHALL share a `PlanningDateGrid` layout primitive for bounded horizontal scrolling, click-and-drag panning, sticky first-column layering, and date-column structure.

#### Scenario: Timeline scrolls inside its owner
- **WHEN** the date range is wider than the card or archive modal
- **THEN** the grid remains inside the owner and exposes horizontal scrolling, including click-and-drag panning

#### Scenario: Sticky first column remains readable
- **WHEN** the grid is horizontally scrolled
- **THEN** the first column remains fixed above date cells with an opaque background and correct z-index

#### Scenario: Timeline groups blocks by date
- **WHEN** one date has one or more assignments
- **THEN** the date cell renders one status group, with block names joined by commas and a single localized status; blocks are not rendered as separate draggable items

#### Scenario: Grid labels match the planning grid
- **WHEN** the timeline is rendered
- **THEN** its first-column labels are `Дата` in the header and `Блок` in the body row

#### Scenario: Expanded archive content stays inside the modal
- **WHEN** an archive row is expanded and its date range is wider than the modal
- **THEN** the timeline remains constrained by the expanded-row width and scrolls horizontally inside it

#### Scenario: Status is visually separated from blocks
- **WHEN** a date has an assignment group
- **THEN** block names are shown on the first line and the localized status on the second line

#### Scenario: Dragging does not select page content
- **WHEN** the user pans a date grid by dragging the mouse
- **THEN** text selection and the browser context menu are suppressed for that drag gesture

### Requirement: Завершённая работа показывает временную раскладку назначений
Карточка завершённой или отменённой работы SHALL показывать отдельную секцию назначений, раскрытую по умолчанию, с непрерывным диапазоном от самой ранней до самой поздней даты неудалённых назначений.

#### Scenario: Карточка содержит назначения
- **WHEN** пользователь открывает карточку терминальной работы с назначениями
- **THEN** он видит таблицу дат от первого до последнего назначения

#### Scenario: В ячейке отображаются только блоки и статусы
- **WHEN** дата содержит одно или несколько назначений
- **THEN** в ячейке отображаются имена блоков отдельными бейджами и локализованный статус каждого назначения, без комментария, исполнителя и времени

#### Scenario: Пустые даты сохраняются в диапазоне
- **WHEN** между первым и последним назначением есть даты без назначений
- **THEN** эти даты остаются видимыми с пустыми ячейками

#### Scenario: Работа без назначений
- **WHEN** у терминальной работы нет неудалённых назначений
- **THEN** секция показывает состояние «Назначений нет»

### Requirement: Архив показывает назначения при раскрытии строки
Архив работ SHALL поддерживать раскрытие строки по клику и отображать в раскрытой области ту же таблицу назначений.

#### Scenario: Строка архива раскрывается
- **WHEN** пользователь раскрывает строку архивной работы
- **THEN** система лениво загружает и показывает временную раскладку назначений этой работы

#### Scenario: Раскрытие не выполняет лишние запросы
- **WHEN** строка архива закрыта или пользователь меняет страницу, поиск либо период
- **THEN** назначения для закрытых строк не запрашиваются, а раскрытые ключи сбрасываются при изменении набора строк

### Requirement: Timeline endpoint возвращает минимальные защищённые данные
Система SHALL предоставлять endpoint чтения временной раскладки одной работы, который проверяет доступ к работе и возвращает только `date`, `block` и `status` для `is_deleted = 0`, отсортированные по дате и идентификатору назначения.

#### Scenario: Доступ к назначениям разрешён
- **WHEN** авторизованный пользователь с доступом к работе запрашивает её timeline
- **THEN** endpoint возвращает все неудалённые назначения с минимальным DTO

#### Scenario: Доступ к чужой работе запрещён
- **WHEN** пользователь запрашивает timeline работы вне доступной команды
- **THEN** endpoint возвращает отказ доступа и не раскрывает назначения

#### Scenario: Буфер обмена не изменяется
- **WHEN** frontend использует `successful-history` для копирования
- **THEN** endpoint и поведение этого сценария остаются без изменений

### Requirement: История изменений терминальной работы закрыта по умолчанию
Добавление timeline SHALL NOT менять существующее состояние истории изменений: при открытии карточки история остаётся скрытой.

#### Scenario: Открытие терминальной работы
- **WHEN** пользователь открывает карточку завершённой или отменённой работы
- **THEN** секция истории изменений закрыта, а секция назначений отображается отдельно
