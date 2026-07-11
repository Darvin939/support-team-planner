# Frontend

React 19 + TypeScript SPA (Vite, Ant Design v6, TanStack Query, React Router, React Flow) для Support Team Planner.
Общее
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

Без актуальной сборки в `dist/` бэкенд не сможет отдать ни одну страницу (`_serve_react_index()` в
`support_planner.py` читает `dist/index.html`) — пересобирайте после каждого изменения фронтенда, если не
используете `npm run dev`.

## Структура

- `public/fonts/` — самостоятельно хостящиеся шрифты (Inter, JetBrains Mono); ссылки на них в `src/index.css`
  Vite сам переписывает под `/react-assets/` при продакшен-сборке и копирует файлы в `dist/fonts/`.
- `src/pages/` — по одному компоненту на маршрут: `LoginPage` (форма логин/пароль, без выбора сотрудника из
  списка), `PlanningPage`, `StatisticsPage`, `JournalPage`, `SettingsPage`.
    - `pages/planning/` — вынесенные части планирования: `TaskModal`/`AssignmentModal` (CRUD-модалки),
      `DependencyGraphModal` (визуализация графа зависимостей задач команды), `HistoryPanel`, `useAssignmentDrag`/
      `useTaskRowDrag` (перетаскивание) и вспомогательные `useAutoScheduleDragScroll`, `useTableDragScroll`,
      `cellTint`, `scrollUtils`.
    - `pages/settings/` — по одному компоненту-вкладке на раздел настроек: `TeamsTab`, `BlocksTab`, `SegmentsTab`,
      `FreezeDaysTab`, `UsersTab`; `SettingsPage.tsx` — просто antd `Tabs`, сохраняющий активную вкладку в
      localStorage.
- `src/components/` — общие UI-компоненты: `AppShell`/`AuthenticatedLayout` (сайдбар, ролевая навигация через
  `GET /api/me`), `MyAccountModal` (смена собственных логина/пароля через `PUT /api/me`), `planningBadges`,
  `FilterGrid` (общая раскладка фильтров на страницах Планирования/Статистики/Журнала), `OverdueNotifications`,
  `StatTile`.
- `src/hooks/` — тонкие обёртки над TanStack Query по доменам данных, плюс `useDateRangeFilter` (период +
  синхронизация с localStorage) и `useIsMobile`.
- `src/lib/` — чистые хелперы: `apiMutate` (обёртка над `fetch` для POST/PUT/PATCH/DELETE), `autoSchedule`
  (авторасписание с учётом дней фриза), `historyFormat` (форматирование истории изменений), `dateFormats`,
  `linkify` (подсветка URL в описаниях задач/назначений как ссылок).
- `src/theme.ts` — токены темы `ConfigProvider` (тёмная/светлая), на основе официальной палитры `@ant-design/colors`.
