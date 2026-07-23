## Context

Team handlers используют `TeamIn`, request-scoped user/role, access helpers и DAO. Создание команды дополнительно
оборачивает create + grant-access в `db.composite_transaction()`. Все зависимости уже находятся вне entrypoint.

## Goals / Non-Goals

**Goals:**
- перенести семь team endpoints в router без изменения поведения;
- сохранить authorization и atomic create semantics;
- проверить OpenAPI и CRUD/access regression.

**Non-Goals:**
- менять team access model или transaction implementation;
- объединять DAO calls в service layer;
- менять frontend.

## Decisions

Router импортирует публично названные access helpers из `access_control`, а не underscore aliases entrypoint.
Handlers переносятся дословно. Atomic scope остаётся непосредственно в create handler. Router подключается рядом с
другими settings routers.

## Risks / Trade-offs

- **[Risk] Потеряется request/session контекст.** → Сохранить `Request` signatures и access tests.
- **[Risk] Создание перестанет быть атомарным.** → Проверить rollback существующими composite tests.
- **[Risk] Dynamic `/api/teams/{team_id}` затронет вложенные paths.** → Зафиксировать OpenAPI и HTTP paths.
