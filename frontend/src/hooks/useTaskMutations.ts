import {message} from 'antd';
import {useMutation, useQueryClient} from '@tanstack/react-query';
import {apiMutate} from '../lib/apiMutate';
import {invalidateTaskData} from '../lib/queryInvalidation';
import {TASK_STATUS_LABELS} from '../domain/types';

export interface TaskPayload {
  task_id?: number;
  team_id: number;
  name: string;
  description: string | null;
  instruction_url: string | null;
  criticality: string;
  psi_status: 'not_required' | 'required' | 'passed';
  segment_id: number;
  dependency_ids: number[];
}

function useTaskMutationInvalidation(options: {activeAssignments?: boolean; dependencies?: boolean} = {}) {
  const queryClient = useQueryClient();
  return () => invalidateTaskData(queryClient, options);
}

export function useSaveTaskMutation(onSuccess: () => void) {
  const invalidate = useTaskMutationInvalidation({dependencies: true});
  return useMutation({
    mutationFn: (payload: TaskPayload) => apiMutate('/api/task', 'POST', payload),
    onSuccess: async () => {
      await invalidate();
      message.success('Сохранено');
      onSuccess();
    },
    onError: (error: Error) => message.error(error.message),
  });
}

export function useDeleteTaskMutation(taskId: number | undefined, onSuccess: () => void) {
  const invalidate = useTaskMutationInvalidation();
  return useMutation({
    mutationFn: () => apiMutate(`/api/task/${taskId}`, 'DELETE'),
    onSuccess: async () => {
      await invalidate();
      message.success('Задача удалена');
      onSuccess();
    },
    onError: (error: Error) => message.error(error.message),
  });
}

export function useRestoreTaskMutation() {
  const invalidate = useTaskMutationInvalidation();
  return useMutation({
    mutationFn: (taskId: number) => apiMutate(`/api/task/${taskId}/restore`, 'POST'),
    onSuccess: async () => {
      await invalidate();
      message.success('Работа восстановлена');
    },
    onError: (error: Error) => message.error(error.message),
  });
}

export function useTaskStatusMutation(getTaskName: (taskId: number) => string | undefined) {
  const invalidate = useTaskMutationInvalidation({activeAssignments: true});
  return useMutation({
    mutationFn: ({taskId, status}: {taskId: number; status: string}) =>
      apiMutate(`/api/tasks/${taskId}/status`, 'PATCH', {status}).then(() => ({taskId, status})),
    onSuccess: async ({taskId, status}) => {
      await invalidate();
      if (status === 'done' || status === 'cancelled') {
        message.success(`«${getTaskName(taskId) ?? taskId}» — ${TASK_STATUS_LABELS[status] ?? status}`);
      }
    },
    onError: (error: Error) => message.error(error.message),
  });
}

export function useTaskReorderMutation(teamId: number | undefined) {
  const invalidate = useTaskMutationInvalidation();
  return useMutation({
    mutationFn: (taskIds: number[]) => apiMutate(`/api/tasks/${teamId}/reorder`, 'PATCH', {task_ids: taskIds}),
    onSuccess: invalidate,
    onError: (error: Error) => message.error(error.message),
  });
}

export function useTaskPriorityMutation() {
  const invalidate = useTaskMutationInvalidation();
  return useMutation({
    mutationFn: ({taskId, position}: {taskId: number; position: 'start' | 'end'}) =>
      apiMutate(`/api/task/${taskId}/priority`, 'PATCH', {position}),
    onSuccess: async () => {
      await invalidate();
      message.success('Приоритет изменён');
    },
    onError: (error: Error) => message.error(error.message),
  });
}
