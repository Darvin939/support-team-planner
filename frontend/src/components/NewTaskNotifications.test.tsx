// @vitest-environment jsdom

import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {MemoryRouter, useLocation} from 'react-router-dom';
import {NewTasksOverviewCard, NewTasksPanel} from './NewTaskNotifications';

const mutate = vi.fn();
const preview = {
  items: [
    {task_id: 10, team_id: 1, task_name: 'Первая работа', team_name: 'Команда А', criticality: 'high',
      task_status: 'new', changed_at: '2026-08-22 10:00:00', author_name: 'Иванов И.'},
    {task_id: 11, team_id: 2, task_name: 'Вторая работа', team_name: 'Команда Б', criticality: 'low',
      task_status: 'done', changed_at: '2026-08-22 11:00:00', author_name: null},
  ],
  total: 35,
  watermark: {changed_at: '2026-08-22 11:00:00', history_id: 50},
};

vi.mock('../hooks/useNewTaskNotifications', () => ({
  useNewTaskNotificationsPreview: vi.fn(() => ({data: preview, isLoading: false, isError: false})),
  useNewTaskNotificationsPage: vi.fn(() => ({data: preview, isLoading: false, isError: false})),
  useMarkNewTasksSeen: vi.fn(() => ({mutate, isPending: false})),
}));

describe('уведомления о новых работах', () => {
  const storage = new Map<string, string>();
  beforeEach(() => {
    storage.clear();
    vi.stubGlobal('sessionStorage', {
      getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => storage.set(key, value),
      clear: () => storage.clear(),
    });
    mutate.mockClear();
    vi.stubGlobal('matchMedia', vi.fn(() => ({
      matches: false, addListener: vi.fn(), removeListener: vi.fn(),
      addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
    })));
  });
  afterEach(cleanup);

  it('группирует preview и подтверждает именно полученный watermark', () => {
    render(<MemoryRouter><NewTasksPanel/></MemoryRouter>);
    expect(screen.getByText('Команда А (1)')).toBeTruthy();
    expect(screen.getByText('Команда Б (1)')).toBeTruthy();
    expect(screen.getByText('Показаны первые 2 из 35')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', {name: 'Отметить все просмотренными'}));
    expect(mutate).toHaveBeenCalledWith(preview.watermark);
  });

  it('закрывает обзор на остаток сессии без подтверждения просмотра', () => {
    const first = render(<MemoryRouter><NewTasksOverviewCard/></MemoryRouter>);
    expect(screen.getByText('Новые работы (35)')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', {name: 'Закрыть обзор'}));
    expect(mutate).not.toHaveBeenCalled();
    first.unmount();
    render(<MemoryRouter><NewTasksOverviewCard/></MemoryRouter>);
    expect(screen.queryByText('Новые работы (35)')).toBeNull();
  });

  it('переходит из Drawer обзора только после его полного закрытия', async () => {
    function LocationProbe() {
      const location = useLocation();
      return <span data-testid="location">{location.pathname}</span>;
    }
    render(<MemoryRouter initialEntries={['/planning']}><NewTasksOverviewCard/><LocationProbe/></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', {name: 'Показать все'}));
    const drawer = await screen.findByRole('dialog');
    fireEvent.click(drawer.querySelector('button[aria-label="Открыть работу Первая работа"]')!);
    expect(screen.getByTestId('location').textContent).toBe('/planning');
    await waitFor(() => expect(screen.getByTestId('location').textContent).toBe('/planning/1'));
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
  });
});
