## Context

Три связанных справочника расположены подряд в `support_planner.py` и используют только `db`, общие request-модели
и `JSONResponse`. Глобальная middleware продолжит защищать маршруты после подключения router.

## Goals / Non-Goals

**Goals:**
- создать первый предметный `APIRouter`;
- сохранить полный HTTP-контракт и порядок middleware;
- подготовить шаблон для последующего переноса других route-групп.

**Non-Goals:**
- менять DAO, валидацию, тексты ошибок или frontend;
- объединять handlers или вводить service layer.

## Decisions

Router размещается в пакете `routers`, сохраняет исходные декораторы и функции почти дословно. Entrypoint вызывает
`app.include_router(reference_data_router)` после настройки middleware и exception handlers. Дублирование
валидации имён не устраняется в этом change, чтобы перенос оставался behavior-preserving.

## Risks / Trade-offs

- **[Risk] Изменится path/operation schema.** → Сравнить OpenAPI paths и выполнить endpoint contract-тесты.
- **[Risk] Middleware перестанет применяться.** → Проверить неавторизованный и недостаточный role access.
- **[Trade-off] Похожая валидация останется.** → Устранить отдельным change после стабилизации routers.
