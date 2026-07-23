import type {Dispatch, SetStateAction} from 'react';
import {message} from 'antd';
import type {Assignment, Task} from '../../hooks/usePlanningData';
import {
  assignmentToPayload,
  useBulkDeleteAssignmentsMutation,
  useBulkRescheduleAssignmentsMutation,
  useSaveAssignmentMutation,
} from '../../hooks/useAssignmentMutations';

export function usePlanningAssignmentActions(options: {
  assignments: Assignment[] | undefined;
  tasks: Task[] | undefined;
  setSelectedAssignmentIds: Dispatch<SetStateAction<Set<number>>>;
}) {
  const saveRescheduledAssignment = useSaveAssignmentMutation({
    successMessage: 'Назначение перенесено',
  });
  const saveAssignmentStatus = useSaveAssignmentMutation({
    includeTasks: true,
    successMessage: 'Статус назначения обновлён',
  });
  const bulkDeleteMutation = useBulkDeleteAssignmentsMutation({
    successMessage: ({deleted}) => `Удалено назначений: ${deleted}`,
    onSuccess: () => options.setSelectedAssignmentIds(new Set()),
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
    bulkDeleteMutation,
    bulkRescheduleMutation,
    isTaskLocked: (taskId: number) => {
      const task = options.tasks?.find((item) => item.id === taskId);
      return !task || task.task_status === 'done' || task.task_status === 'cancelled';
    },
  };
}
