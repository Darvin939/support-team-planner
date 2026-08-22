// @vitest-environment jsdom

import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {MemoryRouter} from 'react-router-dom';
import {OverdueNotifications} from './OverdueNotifications';

const mocks = vi.hoisted(() => ({pageHook: vi.fn()}));
const overdueItems = Array.from({length: 20}, (_, index) => ({
  id: index + 1, task_id: index + 10, team_id: 1, task_name: `Просроченная ${index + 1}`,
  team_name: 'Команда', criticality: 'medium' as const, date: '2026-08-01', status: 'planned' as const,
  user_name: 'Иванов И.', comment: null,
}));

vi.mock('../hooks/usePlanningData', () => ({
  OVERDUE_PREVIEW_LIMIT: 5,
  useOverdueAssignments: () => ({data: {items: overdueItems.slice(0, 5), total: 32}, isLoading: false, isError: false}),
  useOverdueAssignmentsPage: (...args: unknown[]) => mocks.pageHook(...args),
}));
vi.mock('../hooks/useNewTaskNotifications', () => ({
  useNewTaskNotificationsPreview: () => ({data: {items: [], total: 0, watermark: {changed_at: '', history_id: 0}}}),
  useNewTaskNotificationsPage: () => ({data: {items: [], total: 0}, isLoading: false, isError: false}),
  useMarkNewTasksSeen: () => ({mutate: vi.fn(), isPending: false}),
}));

describe('центр просроченных уведомлений', () => {
  beforeEach(() => {
    mocks.pageHook.mockReturnValue({data: {items: overdueItems, total: 32}, isLoading: false, isError: false});
    vi.stubGlobal('matchMedia', vi.fn(() => ({matches: false, addListener: vi.fn(), removeListener: vi.fn(),
      addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn()})));
    vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} });
  });
  afterEach(cleanup);

  it('показывает пять элементов preview и открывает пагинируемый Drawer', async () => {
    render(<MemoryRouter><OverdueNotifications/></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', {name: 'Уведомления'}));
    fireEvent.click(await screen.findByText('Просроченные (32)'));
    expect(await screen.findByText('Показаны первые 5 из 32')).toBeTruthy();
    expect(screen.queryByText('Просроченная 6')).toBeNull();
    fireEvent.click(screen.getByRole('button', {name: 'Показать все'}));
    expect(await screen.findByText('Все просроченные назначения (32)')).toBeTruthy();
    expect(screen.getByText('Просроченная 20')).toBeTruthy();
    expect(mocks.pageHook).toHaveBeenCalledWith(0, 20, true);

    const pageTwo = screen.getByTitle('2');
    fireEvent.click(pageTwo);
    await waitFor(() => expect(mocks.pageHook).toHaveBeenCalledWith(20, 20, true));
  });
});
