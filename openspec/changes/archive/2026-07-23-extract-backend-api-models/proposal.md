## Why

`support_planner.py` одновременно содержит и запуск приложения, и middleware, и маршруты, и все Pydantic-модели
входных данных. Из-за этого файл превышает тысячу строк, а дальнейшее разнесение маршрутов по routers требует
сначала выделить независимый слой API-контрактов.

## What Changes

- Перенести все Pydantic request-модели API из `support_planner.py` в отдельный backend-модуль.
- Сохранить имена классов, типы полей, значения по умолчанию и правила валидации без изменений.
- Импортировать модели в entrypoint и оставить регистрацию маршрутов, middleware и exception handlers на месте.
- Добавить regression-тесты, фиксирующие ключевые validation-сценарии и отсутствие изменений OpenAPI-схемы.
- Не менять публичные HTTP-маршруты, payload, статусы и формат ошибок.

## Capabilities

### New Capabilities

- `backend-api-contract-stability`: публичные request schemas и validation-поведение API сохраняются при внутренней
  декомпозиции backend.

### Modified Capabilities

Нет: существующие требования API и frontend остаются без изменений.

## Impact

- `support_planner.py`: удаление локальных объявлений request-моделей и импорт выделенного модуля.
- Новый backend-модуль API request-моделей.
- `tests/`: структурные и contract regression-тесты.
- Runtime-зависимости, frontend и схема базы данных не изменяются.
