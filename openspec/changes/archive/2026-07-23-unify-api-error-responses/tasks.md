## 1. Backend API-контракт

- [x] 1.1 Добавить общий helper формирования `{"error": "<сообщение>"}` и FastAPI handler для `HTTPException`
  на путях `/api/*`, сохранив status code и строковый `detail`.
- [x] 1.2 Добавить handler для `RequestValidationError` на путях `/api/*` со стабильным строковым сообщением и
  status `422`.
- [x] 1.3 Сохранить стандартное поведение `HTTPException` и validation errors для маршрутов вне `/api/*`.

## 2. Frontend error parser

- [x] 2.1 Вынести общий parser неуспешного response для `apiGet` и `apiMutate`: принимать непустой строковый
  `error`, иначе использовать технический fallback; не поддерживать внутреннее поле `detail`.
- [x] 2.2 Перевести оба API helpers на общий parser без изменения успешных generic/result контрактов.
- [x] 2.3 Добавить минимальную dev-only инфраструктуру frontend unit-тестов, если она отсутствует.

## 3. Автоматические тесты

- [x] 3.1 Добавить backend contract-тесты для ручной API-ошибки, `HTTPException`, validation error и сохранения
  non-API redirect/response semantics.
- [x] 3.2 Добавить frontend unit-тесты parser для `error`, пустого/non-JSON ответа, нестроковых полей и
  одинакового поведения GET/mutation.
- [x] 3.3 Запустить полный backend `pytest`, frontend unit-тесты, lint и production build; устранить регрессии.

## 4. Проверка OpenSpec

- [x] 4.1 Сверить итоговый контракт с `backend-api-error-format` и `frontend-api-error-format`.
- [x] 4.2 Выполнить финальную валидацию OpenSpec change перед sync.
