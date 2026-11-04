// @vitest-environment jsdom

import {cleanup, fireEvent, render, screen, within} from '@testing-library/react';
import {afterEach, beforeAll, describe, expect, it, vi} from 'vitest';
import {TaskArchiveModal} from './TaskArchiveModal';

const mocks = vi.hoisted(() => ({
  timeline: vi.fn(),
  description: null as string | null,
  instructionUrl: null as string | null,
}));

vi.mock('../../hooks/usePlanningData', () => ({
  useTaskArchive: () => ({
    isPending: false,
    data: {
      total: 1,
      tasks: [{
        id: 42,
        name: 'Архивная работа',
        description: mocks.description,
        instruction_url: mocks.instructionUrl,
        criticality: 'medium',
        task_status: 'done',
        psi_status: 'not_required',
        segment_id: 1,
        segment_name: 'Сегмент',
        completed_at: '2026-09-01 12:00:00',
        has_active_assignments: false,
        has_assignments: true,
      }],
    },
  }),
  useTaskAssignmentTimeline: (taskId: number, enabled: boolean) => {
    mocks.timeline(taskId, enabled);
    return {
      data: [
        {date: '2026-09-01', block: 'Анализ', status: 'success'},
        {date: '2026-09-02', block: 'Проверка', status: 'planned'},
      ],
      isLoading: false,
      isError: false,
    };
  },
}));
vi.mock('../../hooks/useTaskMutations', () => ({
  useRestoreTaskMutation: () => ({isPending: false, mutate: vi.fn()}),
}));

beforeAll(() => {
  vi.stubGlobal('ResizeObserver', class {observe() {} unobserve() {} disconnect() {}});
  vi.stubGlobal('matchMedia', vi.fn().mockImplementation(() => ({
    matches: false, addListener: vi.fn(), removeListener: vi.fn(),
    addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
  })));
});

afterEach(() => {
  cleanup();
  mocks.timeline.mockClear();
  mocks.description = null;
  mocks.instructionUrl = null;
});

describe('TaskArchiveModal assignment timeline', () => {
  it('shows an instruction link in a collapsed row without triggering row actions', () => {
    mocks.instructionUrl = 'https://example.com/instruction';
    render(<TaskArchiveModal open teamId={1} canRestore onClose={vi.fn()}/>);
    const link = screen.getByRole('link', {name: 'Инструкция ↗'});
    expect(link.getAttribute('href')).toBe(mocks.instructionUrl);
    expect(link.getAttribute('target')).toBe('_blank');
    expect(link.getAttribute('rel')).toBe('noopener noreferrer');
    fireEvent.click(link);
    expect(screen.queryByRole('region', {name: 'Информация о работе'})).toBeNull();
    expect(screen.queryByText('Восстановить работу?')).toBeNull();
    expect(mocks.timeline).not.toHaveBeenCalled();
  });

  it('shows linked multiline description and labels before assignments when expanded', () => {
    mocks.description = 'Первая строка\nПодробности https://example.com/details';
    render(<TaskArchiveModal open teamId={1} canRestore={false} onClose={vi.fn()}/>);
    expect(screen.queryByRole('region', {name: 'Информация о работе'})).toBeNull();
    fireEvent.click(screen.getByRole('button', {name: 'Expand row'}));
    const info = screen.getByRole('region', {name: 'Информация о работе'});
    expect(info.textContent).toContain('Критичность: Средняя');
    expect(info.textContent).toContain('ПСИ: Не требуется');
    expect(info.textContent).toContain('Первая строка\nПодробности');
    expect(within(info).getByRole('link').getAttribute('href')).toBe('https://example.com/details');
    expect(info.compareDocumentPosition(screen.getByText('Анализ')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(mocks.timeline).toHaveBeenCalledWith(42, true);
  });

  it('omits an empty instruction link and shows a placeholder for an empty description', () => {
    render(<TaskArchiveModal open teamId={1} canRestore={false} onClose={vi.fn()}/>);
    expect(screen.queryByRole('link', {name: 'Инструкция ↗'})).toBeNull();
    fireEvent.click(screen.getByRole('button', {name: 'Expand row'}));
    expect(within(screen.getByRole('region', {name: 'Информация о работе'})).getByText('—')).toBeTruthy();
    expect(screen.getByText('Анализ')).toBeTruthy();
  });

  it('loads timeline only after a row is expanded', () => {
    render(<TaskArchiveModal open teamId={1} canRestore={false} onClose={vi.fn()}/>);
    expect(mocks.timeline).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', {name: 'Expand row'}));
    expect(mocks.timeline).toHaveBeenCalledWith(42, true);
    expect(screen.getByText('Анализ')).toBeTruthy();
    expect(screen.getByText('Проверка')).toBeTruthy();
    expect(screen.getByText('Успешно')).toBeTruthy();
    expect(screen.getByText('Запланировано')).toBeTruthy();
  });
});
