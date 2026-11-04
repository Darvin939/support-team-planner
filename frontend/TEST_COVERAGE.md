# Покрытие изменения bind-task-rollout-template

| Компонент / hook | Тест | Проверяемое поведение |
| --- | --- | --- |
| TaskModal | src/pages/planning/TaskModal.test.tsx | Явный выбор сегмента/шаблона, разрешённые варианты, payload, блокировка и разблокировка, старый NULL, просмотр терминальной работы, состав и порядок компактных групп параметров, сброс ошибок при повторном открытии и новая валидация при submit |
| AssignmentModal | src/pages/planning/AssignmentModal.rollout.test.tsx | Сохранённый шаблон вместо первого доступного, отсутствие выбора, раскладка, payload, причины недоступности, ручное назначение, повторное открытие |
| useAssignmentModalState | Родительский AssignmentModal.rollout.test.tsx | Реальный hook без mock: переключение автоназначения, вычисление дат, сброс состояния при открытии и новый шаблон |
| WorkReferencesTab / TemplatesPanel / useCrudMutations | src/pages/settings/BlocksTab.test.tsx | Ошибка backend при сохранении/удалении, сохранение пользовательского ввода и строки справочника |
| queryInvalidation | src/lib/queryInvalidation.test.ts | Обновление зависимых шаблонов, блоков и работ после изменения справочников |

Production UI и реальный backend проверяются сценарием `tests/ui_task_rollout.py`; артефакты сохраняются в `.tmp/task-rollout-ui`.
