import type {Dispatch, SetStateAction} from 'react';
import {message} from 'antd';
import {useMutation, useQueryClient} from '@tanstack/react-query';
import type {Assignment, Task} from '../../hooks/usePlanningData';
import {apiMutate} from '../../lib/apiMutate';
import {invalidateAssignmentData} from '../../lib/queryInvalidation';
import {
  assignmentToPayload,
  useBulkDeleteAssignmentsMutation,
  useSaveAssignmentMutation,
} from './assignmentMutations';

export function usePlanningAssignmentActions(options: {
  assignments: Assignment[] | undefined;
  tasks: Task[] | undefined;
  setSelectedAssignmentIds: Dispatch<SetStateAction<Set<number>>>;
}) {
  const queryClient = useQueryClient();
  const saveRescheduledAssignment = useSaveAssignmentMutation({successMessage: 'Назначение перенесено'});
  const saveAssignmentStatus = useSaveAssignmentMutation({
    includeTasks: true,
    successMessage: 'Статус назначения обновлён',
  });
  const bulkDeleteMutation = useBulkDeleteAssignmentsMutation({
    onSuccess: (deleted) => {
      options.setSelectedAssignmentIds(new Set());
      message.success(`Удалено назначений: ${deleted}`);
    },
  });
  const bulkRescheduleMutation = useMutation({
    mutationFn: async (moves: {assignmentId: number; taskId: number; newDate: string}[]) => {
      await apiMutate('/api/assignments/bulk-reschedule', 'POST', {
        moves: moves.map((move) => ({assignment_id: move.assignmentId, new_date: move.newDate})),
      });
      return {total: moves.length};
    },
    onSuccess: ({total}) => {
      invalidateAssignmentData(queryClient);
      options.setSelectedAssignmentIds(new Set());
      message.success(`Перенесено назначений: ${total}`);
    },
    onError: (error: Error) => {
      invalidateAssignmentData(queryClient);
      message.error(error.message);
    },
  });

  return {
    rescheduleMutation: {
      mutate: ({assignmentId, newDate}: {assignmentId: number; newDate: string}) => {
        const existing = options.assignments?.find((assignment) => assignment.id === assignmentId);
        if (!existing) return message.error('Назначение не найдено');
        saveRescheduledAssignment.mutate(assignmentToPayload(existing, {date: newDate}));
      },
    },
    assignmentStatusMutation: {
      mutate: ({assignmentId, status}: {assignmentId: number; status: Assignment['status']}) => {
        const existing = options.assignments?.find((assignment) => assignment.id === assignmentId);
        if (!existing) return message.error('Назначение не найдено');
        saveAssignmentStatus.mutate(assignmentToPayload(existing, {status}));
      },
    },
    bulkDeleteMutation,
    bulkRescheduleMutation,
    isTaskLocked: (taskId: number) => {
      const task = options.tasks?.find((item) => item.id === taskId);
      return !task || task.task_status === 'done' || task.task_status === 'cancelled';
    },
  };
}
