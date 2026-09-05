## Матрица покрытия

| Область | Проверка | Результат |
|---|---|---|
| SQLite migration, срок и DAO | `python -m unittest tests.test_new_task_notifications tests.test_sqlite_migrations tests.test_access_control` | 23 теста пройдено |
| Фильтрация новых работ по текущему статусу | `python -m unittest tests.test_new_task_notifications` | 9 тестов пройдено; `done`/`cancelled` исключены, восстановленная `new` возвращается |
| Все backend-регрессии | `python -m unittest discover -s tests` | 122 теста пройдено |
| Автопросмотр и optimistic rollback | Vitest hook/component tests | 87 тестов пройдено |
| Frontend lint | `npm run lint` | ошибок нет; только существующие предупреждения |
| Production frontend | `npm run build` | сборка успешна |
| Production UI | Python Playwright с WAL backup и реальным login | на таблице шириной 3104 px при видимой ширине 686 px строка вне viewport осталась новой и скрылась после пошаговой прокрутки колесом |

## UI-сценарий

Временные работы были созданы от другого пользователя в production БД. После входа администратором первая строка была прокручена в viewport и оставлена видимой 1,8 секунды; запрос preview подтвердил её исчезновение. Целевая строка находилась ниже viewport и осталась в preview, а после ручной прокрутки к ней и 1,8 секунды устойчивой видимости исчезла из preview. После теста backend остановлен, БД восстановлена через SQLite backup API, выполнен `PRAGMA wal_checkpoint(TRUNCATE)` и проверен `PRAGMA integrity_check` (`ok`).

Повторная регрессия использовала production-таблицу шириной 3104 px при видимой ширине 686 px и viewport 1000×600. Целевая нижняя строка оставалась в preview до прокрутки, затем была введена в поле зрения последовательными событиями колеса мыши и исчезла после 1,8 секунды. Это подтверждает, что ширина строки больше не препятствует событию достижения 50% вертикальной видимости.
