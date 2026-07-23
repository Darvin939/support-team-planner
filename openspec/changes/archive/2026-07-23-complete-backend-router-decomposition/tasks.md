## 1. Общие task rules

- [x] 1.1 Перенести загрузку transition map в общий task rules module с сохранением JSON source of truth
- [x] 1.2 Добавить unit-тесты task-lock и transition rules

## 2. Shell и session router

- [x] 2.1 Создать shell router для root, login/logout, `/api/me` и SPA document routes
- [x] 2.2 Перенести static mount, кеш и раздачу React index в shell, оставив в composition root единый вызов регистрации
- [x] 2.3 Добавить regression tests session, redirects, document responses и OpenAPI методов

## 3. Полный task router

- [x] 3.1 Перенести task list/detail/archive/save/restore/delete handlers и общий task serializer
- [x] 3.2 Перенести status/reorder/priority/history handlers с прежними role/access/domain rules
- [x] 3.3 Сохранить составную транзакцию task + dependencies и общий cycle exception
- [x] 3.4 Добавить/расширить API-тесты чтения, lifecycle mutations, ошибок и access-control
- [x] 3.5 Добавить OpenAPI regression checks всех task paths, query parameters и body schemas

## 4. Journal router и composition root

- [x] 4.1 Перенести journal API с нормализацией всех фильтров и team access
- [x] 4.2 Подключить три routers и удалить перенесённые handlers/imports/helpers из `support_planner.py`
- [x] 4.3 Проверить, что entrypoint содержит только сборку приложения, middleware, errors, assets и startup
- [x] 4.4 Добавить API/OpenAPI tests journal filters и отказа доступа

## 5. Итоговая проверка

- [x] 5.1 Запустить targeted regression tests и transaction rollback tests
- [x] 5.2 Запустить полный backend test suite, `py_compile`, `git diff --check` и `openspec validate --all`
