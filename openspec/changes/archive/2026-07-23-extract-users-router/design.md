## Context

GET `/api/users` доступен всем ролям и имеет два response-режима, а mutations требуют admin через middleware.
Delete дополнительно использует текущий session user для доменной проверки.

## Goals / Non-Goals

**Goals:**
- перенести четыре handlers без изменения contracts;
- сохранить method-dependent access policy и session context;
- проверить pagination/full-list и CRUD errors.

**Non-Goals:**
- унифицировать sentinel duplicate returns DAO;
- менять password/login validation;
- менять frontend.

## Decisions

Router импортирует `UserIn`, `db`, `auth`, `Request` и `JSONResponse`; handlers переносятся дословно.
Глобальная middleware продолжает различать GET и mutations по прежней path matrix.

## Risks / Trade-offs

- **[Risk] GET ошибочно станет admin-only.** → Проверить role matrix и non-admin GET.
- **[Risk] Delete потеряет acting user.** → Сохранить Request и regression-тест.
- **[Risk] Изменится full-list/pagination branching.** → Проверить оба режима существующими pagination tests.
