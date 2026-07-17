# planning-table-structure Specification

## Purpose
TBD - created by archiving change split-planning-page-columns. Update Purpose after archive.
## Requirements
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
