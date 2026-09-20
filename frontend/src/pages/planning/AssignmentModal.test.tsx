// @vitest-environment jsdom

import {afterEach, beforeAll, describe, expect, it, vi} from 'vitest';
import {cleanup, render} from '@testing-library/react';
import {App as AntApp} from 'antd';
import {AssignmentModal} from './AssignmentModal';

const mocks = vi.hoisted(() => ({
  saveOptions: undefined as undefined | {onSuccess?: (result: {
    task_completion_suggestion?: {task_id: number; task_name: string};
  }) => void},
}));

vi.mock('../../hooks/usePlanningData', () => ({
  useTeamBlocks: () => ({data: []}),
  useTeamTemplates: () => ({data: []}),
}));

vi.mock('../../hooks/useSettingsData', () => ({
  useTeamAssignees: () => ({data: []}),
}));

vi.mock('../../hooks/useMe', () => ({
  useMe: () => ({data: {role: 'admin'}}),
}));

vi.mock('../../hooks/useIsMobile', () => ({
  useIsMobile: () => false,
}));

vi.mock('../../hooks/useAssignmentMutations', () => ({
  useSaveAssignmentMutation: (options: typeof mocks.saveOptions) => {
    mocks.saveOptions = options;
    return {mutate: vi.fn(), isPending: false};
  },
  useBulkSaveAssignmentsMutation: () => ({mutate: vi.fn(), isPending: false}),
  useDeleteAssignmentMutation: () => ({mutate: vi.fn(), isPending: false}),
}));

vi.mock('./useAssignmentModalState', () => ({
  useAssignmentModalState: () => ({
    autoAssignEnabled: false,
    selectedTemplateId: null,
    autoAssignDates: {},
    autoAssignSelected: null,
    watchedDate: null,
    setSelectedTemplateId: vi.fn(),
    setAutoAssignDates: vi.fn(),
    setAutoAssignSelected: vi.fn(),
    recomputeSchedule: vi.fn(),
    handleAutoAssignToggle: vi.fn(),
  }),
}));

beforeAll(() => {
  vi.stubGlobal('matchMedia', vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })));
});

afterEach(() => {
  cleanup();
  mocks.saveOptions = undefined;
});

describe('AssignmentModal', () => {
  it('forwards a completion suggestion before closing after a successful save', () => {
    const onClose = vi.fn();
    const onTaskCompletionSuggested = vi.fn();
    render(
      <AntApp>
        <AssignmentModal
          open={false}
          teamId={1}
          task={null}
          date={null}
          assignment={null}
          taskAssignments={[]}
          freezeDays={new Set()}
          onClose={onClose}
          onTaskCompletionSuggested={onTaskCompletionSuggested}
        />
      </AntApp>,
    );

    const suggestion = {task_id: 42, task_name: 'Release'};
    mocks.saveOptions?.onSuccess?.({task_completion_suggestion: suggestion});

    expect(onTaskCompletionSuggested).toHaveBeenCalledWith(suggestion);
    expect(onTaskCompletionSuggested.mock.invocationCallOrder[0]).toBeLessThan(onClose.mock.invocationCallOrder[0]);
  });
});
