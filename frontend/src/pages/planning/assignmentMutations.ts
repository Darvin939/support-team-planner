import {message} from 'antd';
import {useMutation, useQueryClient} from '@tanstack/react-query';
import type {Assignment} from '../../hooks/usePlanningData';
import {apiMutate} from '../../lib/apiMutate';
import {invalidateAssignmentData} from '../../lib/queryInvalidation';

export interface AssignmentPayload {
  assignment_id?: number;
  task_id: number;
  date: string;
  block: string | null;
  status: Assignment['status'];
  user_id: number | null;
  comment: string | null;
  time_spent: string | null;
}

export function assignmentToPayload(
  existing: Assignment,
  patch: Partial<Omit<AssignmentPayload, 'assignment_id' | 'task_id'>> = {},
): AssignmentPayload {
  return {
    assignment_id: existing.id,
    task_id: existing.task_id,
    date: existing.date,
    block: existing.block,
    status: existing.status,
    user_id: existing.user_id,
    comment: existing.comment,
    time_spent: existing.time_spent,
    ...patch,
  };
}

export function useSaveAssignmentMutation(options: {
  includeTasks?: boolean;
  successMessage?: string;
  onSuccess?: () => void;
} = {}) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AssignmentPayload) => apiMutate('/api/assignment', 'POST', payload),
    onSuccess: () => {
      invalidateAssignmentData(queryClient, options.includeTasks);
      if (options.successMessage) message.success(options.successMessage);
      options.onSuccess?.();
    },
    onError: (error: Error) => message.error(error.message),
  });
}

export function useDeleteAssignmentMutation(options: { onSuccess?: () => void } = {}) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (assignmentId: number) => apiMutate(`/api/assignment/${assignmentId}`, 'DELETE'),
    onSuccess: () => {
      invalidateAssignmentData(queryClient);
      options.onSuccess?.();
    },
    onError: (error: Error) => message.error(error.message),
  });
}

export function useBulkDeleteAssignmentsMutation(options: {
  onSuccess?: (deleted: number) => void;
} = {}) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (assignmentIds: number[]) =>
      apiMutate('/api/assignments/bulk-delete', 'POST', {assignment_ids: assignmentIds})
        .then(() => ({deleted: assignmentIds.length})),
    onSuccess: ({deleted}) => {
      invalidateAssignmentData(queryClient);
      options.onSuccess?.(deleted);
    },
    onError: (error: Error) => message.error(error.message),
  });
}
