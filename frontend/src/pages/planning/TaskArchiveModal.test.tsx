// @vitest-environment jsdom

import {cleanup, fireEvent, render, screen} from '@testing-library/react';
import {afterEach, beforeAll, describe, expect, it, vi} from 'vitest';
import {TaskArchiveModal} from './TaskArchiveModal';

const mocks = vi.hoisted(() => ({
  timeline: vi.fn(),
}));

vi.mock('../../hooks/usePlanningData', () => ({
  useTaskArchive: () => ({
    isPending: false,
    data: {
      total: 1,
      tasks: [{
        id: 42,
        name: 'Архивная работа',
        description: null,
        instruction_url: null,
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
    return {data: [], isLoading: false, isError: false};
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
});

describe('TaskArchiveModal assignment timeline', () => {
  it('loads timeline only after a row is expanded', () => {
    render(<TaskArchiveModal open teamId={1} canRestore={false} onClose={vi.fn()}/>);
    expect(mocks.timeline).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', {name: 'Expand row'}));
    expect(mocks.timeline).toHaveBeenCalledWith(42, true);
    expect(screen.getByText('Назначений нет')).toBeTruthy();
  });
});
