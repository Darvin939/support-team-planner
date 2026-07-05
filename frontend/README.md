# Frontend

React 19 + TypeScript SPA (Vite, Ant Design v6, TanStack Query, React Router) для Support Team Planner. Общее
описание проекта, API и запуск бэкенда — см. [корневой README](../README.md).

## Команды

```bash
npm install       # установка зависимостей (один раз)
npm run dev       # Vite dev-сервер с HMR — проксирует /api, /login, /logout на бэкенд (:5093),
                  # поэтому параллельно должен быть запущен `python support_planner.py`
npm run build     # продакшен-сборка -> dist/, раздаётся бэкендом по /react-assets/*
npm run preview   # локальный просмотр собранного dist/
npm run lint      # oxlint
```

`dist/` не хранится в репозитории (gitignored) — без сборки бэкенд не сможет отдать ни одну страницу
(`_serve_react_index()` в `support_planner.py` читает `dist/index.html`).

## Структура `src/`

- `pages/` — по одному компоненту на маршрут: `LoginPage`, `PlanningPage`, `StatisticsPage`, `JournalPage`,
  `SettingsPage`. `pages/planning/` — вынесенные части планирования (`TaskModal`, `AssignmentModal`,
  `HistoryPanel`, `useAssignmentDrag` и т. д.).
- `components/` — общие UI-компоненты: `AppShell`/`AuthenticatedLayout` (сайдбар, ролевая навигация через
  `GET /api/me`), `planningBadges`, `StatTile`.
- `hooks/` — тонкие обёртки над TanStack Query по доменам данных.
- `lib/` — чистые хелперы: `apiMutate` (обёртка над `fetch` для POST/PUT/PATCH/DELETE), `autoSchedule`
  (авторасписание с учётом дней фриза), `historyFormat` (форматирование истории изменений).
- `theme.ts` — токены темы `ConfigProvider` (тёмная/светлая), на основе официальной палитры `@ant-design/colors`.
