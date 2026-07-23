## Context

Assignment handlers используют несколько request-моделей, access helpers, форматирование ФИО и общий
`_task_is_locked`, который также нужен task handlers. Active assignments дополнительно использует
`_parse_int_csv`, общий с task dependency endpoints. Прямой импорт helpers из entrypoint создал бы цикл.

## Goals / Non-Goals

**Goals:**
- выделить task-lock rule и CSV query parser без изменения логики;
- перенести шесть assignment endpoints в router;
- сохранить access, history, filters и response shapes.

**Non-Goals:**
- менять lock policy, status transitions или DAO;
- оптимизировать запросы active assignments;
- менять frontend.

## Decisions

Predicate переносится в `task_rules.py`, а parser — в `query_parsing.py`; entrypoint и assignment router импортируют
общие функции. Router получает остальные зависимости из `api_models`, `access_control`, `db` и `utils`. Handler
code переносится механически.

## Risks / Trade-offs

- **[Risk] Task и assignment lock rules разойдутся.** → Оба потребителя используют один helper и regression tests.
- **[Risk] CSV query parsing разойдётся между routes.** → Оба потребителя используют один parser и contract tests.
- **[Risk] Потеряется acting user history.** → Сохранить Request signatures и history tests.
- **[Risk] Изменятся optional pagination/filter branches.** → Зафиксировать OpenAPI и endpoint scenarios.
