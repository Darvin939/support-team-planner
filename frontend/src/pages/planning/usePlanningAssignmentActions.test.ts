import {describe, expect, it, vi} from 'vitest';
import {usePlanningAssignmentActions} from './usePlanningAssignmentActions';
import type {ApiResult} from '../../lib/apiMutate';

const mocks = vi.hoisted(() => ({saveOptions: [] as Array<{onSuccess?: (result: ApiResult) => void}>}));
vi.mock('../../hooks/useAssignmentMutations', () => ({
  useSaveAssignmentMutation: (options: {onSuccess?: (result: ApiResult) => void}) => {
    mocks.saveOptions.push(options);
    return {mutate: vi.fn()};
  },
  useDeleteAssignmentMutation: () => ({mutate: vi.fn()}),
  useBulkDeleteAssignmentsMutation: () => ({mutate: vi.fn()}),
  useBulkRescheduleAssignmentsMutation: () => ({mutate: vi.fn()}),
}));

describe('planning assignment completion delivery', () => {
  it('passes completion results from context-menu status saves without dropping bulk-compatible data', () => {
    mocks.saveOptions = [];
    const receive = vi.fn();
    usePlanningAssignmentActions({assignments: [], tasks: [], setSelectedAssignmentIds: vi.fn(),
      onTaskCompletionSuggested: receive});
    const result = {success: true, task_completion_suggestions: [{task_id: 7, task_name: 'Release'}]};
    mocks.saveOptions[1].onSuccess?.(result);
    expect(receive).toHaveBeenCalledWith(result);
  });
});
