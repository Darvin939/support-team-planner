## Context

Freeze-day API содержит collection routes, специальный `/month` route и catch-all date path. Механический перенос
прост, но порядок регистрации важен, чтобы `month/...` не интерпретировался как дата.

## Goals / Non-Goals

**Goals:**
- перенести пять handlers в отдельный router;
- сохранить порядок routes и все HTTP-контракты;
- проверить month/date операции и access-control.

**Non-Goals:**
- менять формат дат, validation или DAO;
- объединять single/range/month операции;
- менять frontend.

## Decisions

Router объявляет collection и `/month` routes перед `/{date_str:path}` и подключается рядом с reference-data router.
Handlers переносятся без изменения логики. Контракт фиксируется OpenAPI methods и HTTP regression-тестами.

## Risks / Trade-offs

- **[Risk] Catch-all перехватит `/month`.** → Сохранить порядок и проверить оба DELETE route.
- **[Risk] Изменится editor restriction.** → Проверить существующую role matrix и middleware.
- **[Trade-off] Date validation остаётся в handler/DAO.** → Не менять поведение в структурном change.
