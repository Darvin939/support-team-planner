import type {Dispatch, SetStateAction} from 'react';
import {message} from 'antd';
import type {Assignment, Task} from '../../domain/types';
import {
  assignmentToPayload,
  useBulkDeleteAssignmentsMutation,
  useBulkRescheduleAssignmentsMutation,
  useDeleteAssignmentMutation,
  useSaveAssignmentMutation,
} from '../../hooks/useAssignmentMutations';
import type {ApiResult} from '../../lib/apiMutate';
import {isAssignmentDragLocked} from './psiAssignmentPolicy';

export function usePlanningAssignmentActions(options: {
  assignments: Assignment[] | undefined;
  tasks: Task[] | undefined;
  setSelectedAssignmentIds: Dispatch<SetStateAction<Set<number>>>;
  onTaskCompletionSuggested: (result: ApiResult) => void;
}) {
  const saveRescheduledAssignment = useSaveAssignmentMutation({
    successMessage: 'Назначение перенесено',
  });
  const saveAssignmentStatus = useSaveAssignmentMutation({
    successMessage: 'Статус назначения обновлён',
    onSuccess: (result) => {
      options.onTaskCompletionSuggested(result);
    },
  });
  const bulkDeleteMutation = useBulkDeleteAssignmentsMutation({
    successMessage: ({deleted}) => `Удалено назначений: ${deleted}`,
    onSuccess: () => options.setSelectedAssignmentIds(new Set()),
  });
  const deleteAssignmentMutation = useDeleteAssignmentMutation({
    successMessage: 'Назначение удалено',
  });
  const bulkRescheduleMutation = useBulkRescheduleAssignmentsMutation({
    successMessage: ({moved}) => `Перенесено назначений: ${moved}`,
    onSuccess: () => options.setSelectedAssignmentIds(new Set()),
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
    deleteAssignmentMutation,
    bulkDeleteMutation,
    bulkRescheduleMutation,
    isTaskLocked: (taskId: number) => {
      const task = options.tasks?.find((item) => item.id === taskId);
      return !task || task.task_status === 'done' || task.task_status === 'cancelled';
    },
    isAssignmentLocked: (assignment: Assignment) => {
      const task = options.tasks?.find((item) => item.id === assignment.task_id);
      return isAssignmentDragLocked(task, assignment);
    },
  };
}
