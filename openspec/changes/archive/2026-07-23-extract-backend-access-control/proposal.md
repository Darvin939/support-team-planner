## Why

После выделения request-моделей `support_planner.py` всё ещё содержит правила ранжирования ролей, login middleware
и набор access helpers, которыми будут пользоваться будущие routers. Пока эта логика привязана к entrypoint,
безопасно разделить маршруты невозможно.

## What Changes

- Вынести матрицу доступа, authentication middleware и team/task/assignment access helpers в отдельный модуль.
- Оставить регистрацию middleware в FastAPI entrypoint явной.
- Сохранить session, redirect, HTTP status и JSON error semantics без изменений.
- Добавить regression-тесты для публичных/защищённых путей и ролевого доступа.
- Не менять маршруты, payload или frontend.

## Capabilities

### New Capabilities

Нет.

### Modified Capabilities

- `backend-api-contract-stability`: внутренняя декомпозиция сохраняет также authentication и authorization
  semantics.

## Impact

- `support_planner.py`: удаление access-control helpers и импорт выделенного модуля.
- Новый backend-модуль access-control.
- Backend regression-тесты; frontend, база данных и runtime-зависимости не изменяются.
