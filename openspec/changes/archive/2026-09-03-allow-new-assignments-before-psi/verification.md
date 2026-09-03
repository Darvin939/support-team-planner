## Матрица покрытия требований

| Требование | Автоматическая проверка |
|---|---|
| Создание `new` при `required`, запрет других статусов | `tests/test_composite_transactions.py::test_required_psi_allows_only_new_planning_and_bulk_is_atomic` |
| Успешное автоназначение и атомарный отказ bulk upsert | тот же backend-сценарий с допустимым и смешанным bulk-набором |
| Редактирование и удаление `new` с сохранением ролевых правил | backend-сценарий выполняется под `transaction-user`; существующие role-policy тесты остаются зелёными |
| Запрет активации `new` и возврата legacy в `new` | backend-сценарий одиночного сохранения |
| Только comment/time для legacy-назначения | backend-сценарий проверяет допустимое обновление и запрет даты/статуса/переноса |
| Перенос `new`, запрет переноса другого статуса | backend-сценарий bulk-reschedule и `psiAssignmentPolicy.test.ts` |
| Изменение требования ПСИ при только `new` | `test_psi_requirement_can_change_with_only_new_assignments` и `TaskModal.test.tsx` |
| Блокировка требования ПСИ при активном назначении | те же backend и component-тесты с `has_active_assignments` |
| Доступность пустой ячейки и `new`, блокировка legacy | `psiAssignmentPolicy.test.ts` и логика `usePlanningColumns` используют единый предикат |
| Фиксированный статус и пояснение при `required` | `AssignmentModal` использует единый PSI-предикат; поле статуса отключено и warning задан согласованным текстом |

## Выполненные проверки

- `python -m unittest tests.test_composite_transactions tests.test_task_archive` — 28 тестов пройдено.
- `npm test` — 23 файла, 80 тестов пройдено.
- `npm run lint` — ошибок нет; остаются существующие предупреждения проекта.
- `npm run build` — TypeScript и production-сборка успешно завершены.
- Production UI-сценарий на Python + Playwright — алерт ПСИ расположен отдельной строкой над формой назначения; проверено сравнением bounding box на viewport 1440×1000.
