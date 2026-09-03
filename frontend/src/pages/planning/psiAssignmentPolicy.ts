import type {Assignment, AssignmentStatus, PsiStatus, Task} from '../../domain/types';

export function isPsiPlanningBlocked(
  psiStatus: PsiStatus,
  assignmentStatus: AssignmentStatus | null,
): boolean {
  return psiStatus === 'required' && assignmentStatus !== null && assignmentStatus !== 'new';
}

export function isAssignmentDragLocked(task: Task | undefined, assignment: Assignment): boolean {
  return !task
    || task.task_status === 'done'
    || task.task_status === 'cancelled'
    || isPsiPlanningBlocked(task.psi_status, assignment.status);
}
