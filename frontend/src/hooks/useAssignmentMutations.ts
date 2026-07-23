import {message} from 'antd';
import {useMutation, useQueryClient} from '@tanstack/react-query';
import type {Assignment} from './usePlanningData';
import {apiMutate} from '../lib/apiMutate';
import {invalidateAssignmentData} from '../lib/queryInvalidation';

export interface AssignmentPayload {
  assignment_id?: number | null;
  task_id: number;
  date: string;
  block: string | null;
  status: Assignment['status'];
  user_id: number | null;
  comment: string | null;
  time_spent: string | null;
}

interface MutationOptions<TResult = void> {
  includeTasks?: boolean;
  successMessage?: string | ((result: TResult) => string);
  onSuccess?: (result: TResult) => void;
}

function showSuccess<TResult>(
  successMessage: MutationOptions<TResult>['successMessage'],
  result: TResult,
) {
  if (!successMessage) return;
  message.success(typeof successMessage === 'function' ? successMessage(result) : successMessage);
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

export function useSaveAssignmentMutation(options: MutationOptions = {}) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AssignmentPayload) => apiMutate('/api/assignment', 'POST', payload),
    onSuccess: () => {
      invalidateAssignmentData(queryClient, options.includeTasks);
      showSuccess(options.successMessage, undefined);
      options.onSuccess?.();
    },
    onError: (error: Error) => message.error(error.message),
  });
}

export function useDeleteAssignmentMutation(options: MutationOptions = {}) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (assignmentId: number) => apiMutate(`/api/assignment/${assignmentId}`, 'DELETE'),
    onSuccess: () => {
      invalidateAssignmentData(queryClient, options.includeTasks);
      showSuccess(options.successMessage, undefined);
      options.onSuccess?.();
    },
    onError: (error: Error) => message.error(error.message),
  });
}

export function useBulkSaveAssignmentsMutation(options: MutationOptions<{saved: number}> = {}) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (assignments: AssignmentPayload[]) =>
      apiMutate('/api/assignments/bulk', 'POST', {assignments})
        .then(() => ({saved: assignments.length})),
    onSuccess: (result) => {
      invalidateAssignmentData(queryClient, options.includeTasks);
      showSuccess(options.successMessage, result);
      options.onSuccess?.(result);
    },
    onError: (error: Error) => message.error(error.message),
  });
}

export function useBulkDeleteAssignmentsMutation(options: MutationOptions<{deleted: number}> = {}) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (assignmentIds: number[]) =>
      apiMutate('/api/assignments/bulk-delete', 'POST', {assignment_ids: assignmentIds})
        .then(() => ({deleted: assignmentIds.length})),
    onSuccess: (result) => {
      invalidateAssignmentData(queryClient, options.includeTasks);
      showSuccess(options.successMessage, result);
      options.onSuccess?.(result);
    },
    onError: (error: Error) => message.error(error.message),
  });
}

export interface AssignmentMove {
  assignmentId: number;
  newDate: string;
}

export function useBulkRescheduleAssignmentsMutation(options: MutationOptions<{moved: number}> = {}) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (moves: AssignmentMove[]) =>
      apiMutate('/api/assignments/bulk-reschedule', 'POST', {
        moves: moves.map((move) => ({assignment_id: move.assignmentId, new_date: move.newDate})),
      }).then(() => ({moved: moves.length})),
    onSuccess: (result) => {
      invalidateAssignmentData(queryClient, options.includeTasks);
      showSuccess(options.successMessage, result);
      options.onSuccess?.(result);
    },
    onError: (error: Error) => {
      invalidateAssignmentData(queryClient, options.includeTasks);
      message.error(error.message);
    },
  });
}
