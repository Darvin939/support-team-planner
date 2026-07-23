import {useMemo, useState} from 'react';
import type {Assignment, Task} from '../../domain/types';

export function usePlanningFilters(tasks: Task[] | undefined, assignmentsByTask: Map<number, Assignment[]>) {
  const [criticalities, setCriticalities] = useState<string[]>([]);
  const [assignmentStatuses, setAssignmentStatuses] = useState<string[]>([]);
  const [taskStatuses, setTaskStatuses] = useState<string[]>([]);
  const [segmentIds, setSegmentIds] = useState<number[]>([]);

  const filteredTasks = useMemo(() => (tasks ?? []).filter((task) => {
    if (criticalities.length && !criticalities.includes(task.criticality)) return false;
    if (taskStatuses.length && !taskStatuses.includes(task.task_status)) return false;
    if (segmentIds.length && !segmentIds.includes(task.segment_id)) return false;
    if (assignmentStatuses.length) {
      const assignments = assignmentsByTask.get(task.id) ?? [];
      if (!assignments.some((assignment) => assignmentStatuses.includes(assignment.status))) return false;
    }
    return true;
  }), [tasks, criticalities, taskStatuses, segmentIds, assignmentStatuses, assignmentsByTask]);

  return {
    criticalities, setCriticalities,
    assignmentStatuses, setAssignmentStatuses,
    taskStatuses, setTaskStatuses,
    segmentIds, setSegmentIds,
    filteredTasks,
  };
}
