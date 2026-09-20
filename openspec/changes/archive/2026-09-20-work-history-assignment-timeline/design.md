## Context

В `TaskModal` завершённая работа показывает только метаданные и отдельную историю изменений. В `TaskArchiveModal` строки архива не имеют дочернего содержимого. Назначения уже хранят дату, строку блока и статус, а автопланирование использует горизонтальную таблицу с датами по колонкам.

## Goals / Non-Goals

**Goals:**

- Переиспользовать один read-only компонент временной раскладки в карточке и архиве.
- Показывать весь диапазон дат от min до max неудалённых назначений.
- Передавать только `date`, `block`, `status` и не загружать комментарии, исполнителей или время.
- Избежать N+1 для закрытых строк архива через lazy-загрузку и React Query cache.
- Сохранить историю изменений скрытой по умолчанию.

**Non-Goals:**

- Изменение создания, редактирования, удаления или копирования назначений.
- Изменение endpoint `successful-history`.
- Редактирование назначений из новой таблицы.

## Decisions

### 1. Отдельный компактный endpoint

Добавить `GET /api/task/{task_id}/assignment-timeline`. Endpoint проверяет доступ к работе через существующий `require_task_access` и возвращает массив `{date, block, status}` для `is_deleted = 0`, отсортированный по `date, id`. Запрос выбирает только нужные колонки и использует существующий индекс по `task_id`.

Альтернативы: расширять `/api/tasks/{team_id}/archive` назначениями (лишний трафик для каждой строки) или переиспользовать `successful-history` (неполный набор статусов и другой сценарий). Оба варианта отклонены.

### 2. Общий компонент Timeline

`AssignmentTimeline` принимает минимальный список назначений, вычисляет min/max даты, генерирует непрерывный диапазон и отображает даты колонками в горизонтально прокручиваемой таблице. В каждой ячейке блоки разделяются по запятой и выводятся отдельными бейджами со статусом. Статусы используют общий `ASSIGNMENT_STATUS_LABELS` и цветовую схему планировщика.

При пустом списке компонент показывает «Назначений нет». Состояния loading/error передаются контейнером.

### 3. Интеграция и загрузка

Для терминальной `TaskModal` новый hook `useTaskAssignmentTimeline(taskId, enabled)` включается только при открытой карточке и наличии task ID; секция назначения размещается под метаданными. `useHistoryToggle` для истории не меняется, поэтому история остаётся закрытой по умолчанию.

`TaskArchiveModal` использует `Table` expandable: раскрытие строки запускает hook для её task ID. Раскрытые ключи сбрасываются при смене страницы, поиска или периода. Query key включает task ID, а закрытые строки не выполняют запросов.

### 4. Безопасность и совместимость

Endpoint не принимает team ID от клиента как источник авторизации: доступ определяется самой работой. Удалённые назначения не возвращаются. Формат существующих Assignment API и buffer-copy сценарий не меняются.

## Risks / Trade-offs

- [Большой диапазон дат создаёт широкую таблицу] → использовать горизонтальный scroll и компактные ячейки, как в автопланировании.
- [Несколько блоков в строковом поле `block`] → разделять по запятым только на frontend, сохраняя исходные данные неизменными.
- [Много раскрытых строк архива] → lazy-load, кэширование React Query и сброс expanded keys при изменении набора строк.
- [Назначение без корректного статуса] → показывать исходное значение как fallback вместо потери данных.

## Migration Plan

Миграция БД не требуется. Сначала разворачивается backend endpoint, затем frontend. Откат frontend безопасен: старый клиент не вызывает новый endpoint.

## Open Questions

## UI layout revision

The assignment timeline must reuse a shared `PlanningDateGrid` layout primitive with the auto-scheduling grid. The primitive owns the bounded horizontal-scroll container, click-and-drag horizontal scrolling, sticky first column, opaque sticky backgrounds, and z-index layering. It exposes render slots for date headers, row label, and date cells.

The auto-scheduling grid keeps its existing interactive block rendering and drag/drop behavior. The history timeline uses the same layout primitive but renders one status group per date; block names are joined with commas inside that group and are not separate draggable elements. The timeline's first column labels are `Дата` in the header and `Блок` in the body row.

Нет.
