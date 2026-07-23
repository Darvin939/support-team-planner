## Context

Authentication middleware, path-to-role rules and entity access helpers находятся в `support_planner.py`.
Маршруты напрямую вызывают эти helpers, поэтому они являются общей зависимостью будущих router-модулей.

## Goals / Non-Goals

**Goals:**

- выделить access-control в модуль без зависимости от FastAPI app;
- сохранить точный порядок authentication, role и entity-access проверок;
- оставить регистрацию middleware видимой в entrypoint;
- покрыть поведение ролей и redirect/error regression-тестами.

**Non-Goals:**

- менять матрицу ролей или session format;
- переходить на FastAPI dependency injection;
- перемещать routes или менять frontend/API contracts.

## Decisions

### Модуль экспортирует middleware-функцию и access helpers

Новый `access_control.py` содержит `_required_rank`, `require_login`, `_access_user` и entity/team helpers.
Entrypoint регистрирует импортированную middleware-функцию через `app.middleware('http')`, сохраняя порядок
относительно request-scoped DB middleware.

### Сначала механический перенос, DI отдельно

Helpers продолжают использовать текущие `auth` и `db` модули. Передача repository/dependency объектов сделала бы
изменение архитектурным переписыванием и затруднила бы проверку эквивалентности.

### Frontend не затрагивается

Redirect, status и JSON payload остаются прежними, поэтому публичный контракт не меняется. Любое обнаруженное
изменение контракта требует пересмотра change и синхронного изменения frontend.

## Risks / Trade-offs

- **[Risk] Изменится порядок middleware.** → Регистрировать функции в прежнем порядке и проверить protected route.
- **[Risk] Потеряется отдельное правило path/method.** → Зафиксировать матрицу parametrized-тестом.
- **[Risk] Возникнет циклический импорт.** → Access-модуль не импортирует `support_planner` или `app`.
- **[Trade-off] Helpers остаются связаны с глобальными DAO.** → Dependency injection вынести в отдельный change.
