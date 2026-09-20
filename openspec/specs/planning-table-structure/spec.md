# planning-table-structure Specification

## Purpose
TBD - created by archiving change split-planning-page-columns. Update Purpose after archive.
## Requirements
### Requirement: Assignment timelines use a shared bounded date-grid layout
The terminal task card and expandable archive rows SHALL expose a read-only assignment timeline using the shared `PlanningDateGrid` layout primitive. The primitive SHALL provide bounded horizontal scrolling, click-and-drag panning without text selection or browser context menus, sticky opaque first-column layering, and safe rendering inside modal/expanded-row width constraints. The auto-scheduling grid SHALL reuse this layout and drag-scroll mechanism while retaining its own interactive draggable block behavior.

#### Scenario: Timeline remains inside an archive modal
- **WHEN** an expanded archive task has assignments spanning more dates than fit in the modal
- **THEN** the expanded row remains constrained to the modal width and the timeline scrolls horizontally inside it

#### Scenario: Timeline groups blocks and status by date
- **WHEN** a date has one or more non-deleted assignments
- **THEN** one group is rendered for that date, block names are comma-separated on the first line, and one localized status is rendered on the second line

#### Scenario: Timeline labels and sticky column
- **WHEN** the timeline is rendered and horizontally scrolled
- **THEN** the first-column labels are `Дата` and `Блок`, and the first column remains readable above date cells

#### Scenario: Grid drag does not select content
- **WHEN** the user pans either date grid with a mouse drag
- **THEN** text selection and the browser context menu are suppressed for the drag gesture

### Requirement: Task assignment timeline data is minimal and access-controlled
The system SHALL provide `GET /api/task/{task_id}/assignment-timeline`, returning only `date`, `block`, and `status` for non-deleted assignments ordered by date and assignment id, after checking access to the task. Archive timeline data SHALL be loaded lazily per expanded row and cached by task id; closed rows SHALL not issue requests. The existing `successful-history` clipboard behavior SHALL remain unchanged.

#### Scenario: Authorized timeline request
- **WHEN** an authorized user requests the timeline for an accessible task
- **THEN** the endpoint returns the sorted minimal DTO rows and excludes deleted assignments

#### Scenario: Unauthorized timeline request
- **WHEN** a user requests a task outside their access scope
- **THEN** the endpoint rejects the request without exposing assignments

### Requirement: Terminal task history remains collapsed by default
Adding the assignment timeline SHALL NOT open the existing change-history panel automatically when a terminal task card is opened.

#### Scenario: Terminal card opens
- **WHEN** a user opens a completed or cancelled task card
- **THEN** the assignment timeline is shown separately and the existing change-history panel remains collapsed

### Requirement: Planning table columns behave identically after extraction
The Planning page's table (task-name column with context menu/dependency badges/status dropdown, plus per-date
schedule-chip columns) SHALL render and behave identically whether its column definitions live inline in
`PlanningPage.tsx` or in an extracted module.

#### Scenario: Task-name column context menu unchanged
- **WHEN** a user right-clicks a task row's name cell
- **THEN** the same context menu (priority move to start/end of tier, etc.) appears, offering the same items as
  before the extraction

#### Scenario: Dependency badges unchanged
- **WHEN** a task has dependencies
- **THEN** the same dependency badge(s) render in the name column, identical to pre-extraction behavior

#### Scenario: Status/priority dropdown unchanged
- **WHEN** a user interacts with the status or priority control in the name column
- **THEN** the same options are offered and the same mutations fire as before extraction

#### Scenario: Schedule-chip columns unchanged
- **WHEN** the table renders per-date columns for the selected date range
- **THEN** each date column shows the same assignment chips, with the same drag-and-drop and click behavior as
  before extraction

### Requirement: Ячейка работы показывает сегмент
Таблица планирования SHALL показывать название сегмента каждой работы как вторичную метаинформацию под её названием.

#### Scenario: Сегмент виден в списке работ
- **WHEN** таблица отображает работу с заполненным `segment_name`
- **THEN** под названием работы показана строка `Сегмент: <segment_name>` вторичным цветом

#### Scenario: Длинное название не расширяет колонку
- **WHEN** название сегмента не помещается в доступную ширину
- **THEN** текст обрезан многоточием, а полное название доступно как подсказка

### Requirement: Внешний клик сначала закрывает контекстное меню
Таблица планирования MUST поглощать первый клик вне любого открытого контекстного `Dropdown`, чтобы этот клик только закрывал меню и не запускал действие элемента под курсором.

#### Scenario: Меню назначения не открывает modal после dismiss-click
- **WHEN** контекстное меню назначения открыто и пользователь кликает по календарной ячейке вне popup
- **THEN** меню закрывается, а модальное окно назначения не открывается

#### Scenario: Меню работы не открывает modal после dismiss-click
- **WHEN** контекстное меню ячейки «Работа» открыто и пользователь кликает по кнопке редактирования или другому интерактивному элементу вне popup
- **THEN** меню закрывается, а никакое модальное окно не открывается

#### Scenario: Следующий клик выполняет обычное действие
- **WHEN** меню уже закрыто предыдущим кликом и пользователь повторно кликает по тому же доступному элементу
- **THEN** его обычное действие, включая открытие соответствующего modal, выполняется

#### Scenario: Выбор пункта меню
- **WHEN** пользователь выбирает пункт внутри открытого меню
- **THEN** действие пункта выполняется, а никакое модальное окно не открывается

### Requirement: Согласованная первоначальная отрисовка таблицы планирования
Система SHALL показывать таблицу планирования только после завершения загрузки списка работ и всех данных текущей страницы, влияющих на строки и ячейки таблицы. До этого система SHALL показывать индикатор загрузки вместо пустой или частично заполненной таблицы.

#### Scenario: Последовательная загрузка непустой страницы
- **WHEN** список работ загружен, но назначения, зависимости или данные нерабочих дней для таблицы ещё загружаются
- **THEN** система показывает индикатор загрузки и не монтирует planning grid

#### Scenario: Все данные страницы загружены
- **WHEN** список работ и все влияющие на таблицу данные текущей страницы успешно загружены
- **THEN** система заменяет индикатор загрузки полностью сформированной таблицей

#### Scenario: Страница не содержит работ
- **WHEN** запрос списка работ успешно завершён с пустым результатом и зависимые от идентификаторов работ запросы не запускаются
- **THEN** система завершает состояние загрузки и показывает empty-состояние

#### Scenario: Ошибка обязательных данных таблицы
- **WHEN** один из обязательных для первоначальной таблицы запросов завершается ошибкой
- **THEN** система прекращает показывать индикатор загрузки и не показывает частично сформированную таблицу

### Requirement: Центрирование готовой таблицы на сегодняшней дате
Система SHALL выполнять автоматическое горизонтальное центрирование на сегодняшней дате только после монтирования полностью сформированной таблицы. Система SHALL повторно центрировать таблицу после изменения её представления и SHALL сохранять пользовательскую позицию при фоновых обновлениях, не изменяющих представление.

#### Scenario: Центрирование после согласованной загрузки
- **WHEN** все обязательные данные загружены и planning grid с ячейкой сегодняшней даты смонтирован
- **THEN** система центрирует видимую область таблицы на сегодняшней дате

#### Scenario: Зависимые данные догружаются
- **WHEN** список работ уже получен, но зависимые данные таблицы ещё не завершили первоначальную загрузку
- **THEN** система не выполняет преждевременное центрирование по промежуточной разметке

#### Scenario: Изменение серверного представления
- **WHEN** пользователь меняет команду, период, серверный поиск, режим показа завершённых работ, страницу или размер страницы
- **THEN** система центрирует полностью загруженное новое представление на сегодняшней дате

#### Scenario: Изменение клиентского фильтра
- **WHEN** пользователь меняет фильтр критичности, сегмента, статуса назначения или статуса работы
- **THEN** система центрирует актуальный отфильтрованный grid на сегодняшней дате

#### Scenario: Структурное изменение состава работ
- **WHEN** добавление, удаление или изменение статуса меняет набор работ текущего серверного представления
- **THEN** система центрирует обновлённый grid на сегодняшней дате

#### Scenario: Изменение порядка без изменения состава
- **WHEN** порядок работ меняется, но набор идентификаторов текущего представления остаётся прежним
- **THEN** система сохраняет текущую горизонтальную позицию пользователя

#### Scenario: Фоновое обновление показанной таблицы
- **WHEN** данные уже были успешно показаны и обновляются назначения, зависимости, нерабочие дни или тот же набор работ без изменения параметров представления
- **THEN** система не заменяет готовую таблицу индикатором первоначальной загрузки и сохраняет текущую горизонтальную позицию пользователя

### Requirement: Фильтр работы использует актуальные статусы
Фильтр статуса работы в планировщике SHALL предлагать только актуальные значения `new`, `done`, `cancelled` и MUST NOT предлагать упразднённые `ready` или `in_progress`.

#### Scenario: Открытие фильтра статуса работы
- **WHEN** пользователь открывает варианты фильтра статуса работы
- **THEN** доступны только `Новый`, `Выполнено` и `Отменено`

### Requirement: Frontend использует типизированные централизованные перечисления
Frontend SHALL определять актуальные options и labels для статуса работы, статуса назначения, критичности, ПСИ и роли в централизованных типизированных источниках и MUST NOT поддерживать независимые локальные копии тех же подписей.

#### Scenario: Статистика отображает статус назначения
- **WHEN** таблица статистики показывает статус назначения
- **THEN** подпись берётся из общей карты статусов назначения

#### Scenario: История отображает ПСИ
- **WHEN** журнал показывает изменение `psi_status`
- **THEN** подпись берётся из общей карты ПСИ с fallback для неизвестного исторического значения

#### Scenario: Компилятор проверяет полноту карт
- **WHEN** актуальный union-тип перечисления изменяется
- **THEN** TypeScript требует согласованно обновить типизированные options/labels, которые должны покрывать этот набор

### Requirement: Индикатор критичности встроен в первую строку названия работы
Ячейка работы SHALL показывать индикатор критичности непосредственно перед текстом заголовка в его первой строке и MUST NOT резервировать ширину индикатора слева от последующих строк многострочного заголовка.

#### Scenario: Однострочное название
- **WHEN** название работы помещается в одну строку
- **THEN** индикатор критичности отображается перед названием с небольшим визуальным интервалом

#### Scenario: Многострочное название
- **WHEN** название работы переносится на две или более строки
- **THEN** индикатор присутствует только в первой строке, а каждая последующая строка начинается от левого края текстовой области ячейки

#### Scenario: Поведение индикатора сохранено
- **WHEN** пользователь наводит курсор на индикатор критичности или взаимодействует с ячейкой работы
- **THEN** текущие обозначение, цвет, подсказка и доступные действия работают как до изменения компоновки

### Requirement: Планировщик предоставляет компактные пресеты периода
Поле периода на странице планировщика SHALL предоставлять пресеты `Прошлые 30 дней`, `Прошлые 7`, `Эта неделя`, `±7 дней` и `±14 дней`, включая прошедшие назначения и передавая выбранный диапазон через существующий обработчик фильтра.

#### Scenario: Доступны все пресеты
- **WHEN** пользователь открывает календарь периода в планировщике
- **THEN** он видит все пять согласованных подписей

#### Scenario: Выбраны исторические 30 дней
- **WHEN** пользователь выбирает `Прошлые 30 дней`
- **THEN** диапазон содержит сегодня и 29 предыдущих календарных дней

#### Scenario: Выбраны исторические 7 дней
- **WHEN** пользователь выбирает `Прошлые 7`
- **THEN** диапазон содержит сегодня и 6 предыдущих календарных дней

#### Scenario: Выбрана текущая неделя
- **WHEN** пользователь выбирает `Эта неделя`
- **THEN** диапазон идёт с понедельника по воскресенье текущей календарной недели

#### Scenario: Выбран горизонт ±7 дней
- **WHEN** пользователь выбирает `±7 дней`
- **THEN** диапазон содержит 6 предыдущих дней, сегодня и 7 следующих дней

#### Scenario: Выбран горизонт ±14 дней
- **WHEN** пользователь выбирает `±14 дней`
- **THEN** диапазон содержит 13 предыдущих дней, сегодня и 14 следующих дней

### Requirement: Календарь периода начинается с понедельника
Календарь DatePicker в планировщике SHALL использовать русскую локаль с понедельником как первым днём недели.

#### Scenario: Отображение недели
- **WHEN** пользователь открывает календарь периода
- **THEN** первым столбцом календаря отображается понедельник

### Requirement: Пресеты не заменяют ручной выбор
Пользователь SHALL сохранять возможность выбрать произвольный допустимый диапазон, очистить его и восстановить сохранённый диапазон через localStorage с использованием существующего обработчика.

#### Scenario: Ручной диапазон и очистка
- **WHEN** пользователь задаёт произвольный диапазон или очищает поле периода
- **THEN** планировщик обрабатывает действие существующим callback и сохраняет прежнее поведение

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

