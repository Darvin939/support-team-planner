import {useMemo, useState} from 'react';
import type {Assignment, AssignmentStatus, Criticality, PsiStatus, Task} from '../../domain/types';

export function usePlanningFilters(tasks: Task[] | undefined, assignmentsByTask: Map<number, Assignment[]>) {
  const [criticalities, setCriticalities] = useState<Criticality[]>([]);
  const [assignmentStatuses, setAssignmentStatuses] = useState<AssignmentStatus[]>([]);
  const [psiStatuses, setPsiStatuses] = useState<PsiStatus[]>([]);
  const [segmentIds, setSegmentIds] = useState<number[]>([]);

  const filteredTasks = useMemo(() => (tasks ?? []).filter((task) => {
    if (criticalities.length && !criticalities.includes(task.criticality)) return false;
    if (psiStatuses.length && !psiStatuses.includes(task.psi_status)) return false;
    if (segmentIds.length && !segmentIds.includes(task.segment_id)) return false;
    if (assignmentStatuses.length) {
      const assignments = assignmentsByTask.get(task.id) ?? [];
      if (!assignments.some((assignment) => assignmentStatuses.includes(assignment.status))) return false;
    }
    return true;
  }), [tasks, criticalities, psiStatuses, segmentIds, assignmentStatuses, assignmentsByTask]);

  return {
    criticalities, setCriticalities,
    assignmentStatuses, setAssignmentStatuses,
    psiStatuses, setPsiStatuses,
    segmentIds, setSegmentIds,
    filteredTasks,
  };
}
