## Матрица покрытия требований

| Требование | Автоматическая проверка |
|---|---|
| Полная история успешных назначений работы | `tests/test_successful_assignment_copy.py`: DAO и endpoint возвращают назначения вне экранного диапазона |
| Исключение других статусов и soft-delete | `tests/test_successful_assignment_copy.py::test_dao_returns_only_successful_undeleted_task_history_in_date_order` |
| Доступ к команде и принадлежность работы | `tests/test_successful_assignment_copy.py::test_endpoint_checks_team_access_and_task_membership` |
| Последняя успешная дата уникального блока | `frontend/src/pages/planning/successfulAssignmentCopy.test.ts` |
| Разбор составных и пустых блоков | `frontend/src/pages/planning/successfulAssignmentCopy.test.ts` |
| Группировка, сортировка и формат текста | `frontend/src/pages/planning/successfulAssignmentCopy.test.ts` |
| Действие для read-only и терминальной работы | `frontend/src/pages/planning/usePlanningColumns.test.tsx`: сценарий терминальной работы под ролью пользователя |
| Успешная запись в Clipboard API | `frontend/src/pages/planning/usePlanningColumns.test.tsx`: проверка точного текста и уведомления |
| Пустой результат не меняет буфер | `frontend/src/pages/planning/usePlanningColumns.test.tsx`: проверка отсутствия вызова Clipboard API |
| Ошибка загрузки или Clipboard API | `frontend/src/pages/planning/usePlanningColumns.test.tsx`: оба источника ошибки и уведомление |

## Выполненные проверки

- `python -m unittest tests.test_successful_assignment_copy tests.test_team_access_api` — 11 тестов пройдено.
- `npm test -- --run src/pages/planning/successfulAssignmentCopy.test.ts src/pages/planning/usePlanningColumns.test.tsx` — 9 тестов пройдено.
- `npm run lint` — ошибок нет; сохранены существующие предупреждения проекта.
- `npm run build` — TypeScript и production-сборка успешно завершены.
- Полный `npm test` — 68 тестов пройдено, 8 существующих тестов `TaskModal.test.tsx` падают из-за несовпадения ожидаемой подписи «ПСИ требуется» с фактической «Требуется ПСИ».
