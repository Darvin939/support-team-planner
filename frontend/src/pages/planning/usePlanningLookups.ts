import {useMemo} from 'react';
import type {Assignment, TaskDep} from '../../domain/types';

export function usePlanningLookups(assignments: Assignment[] | undefined, deps: TaskDep[] | undefined) {
  return useMemo(() => {
    const assignmentByKey = new Map<string, Assignment>();
    const assignmentById = new Map<number, Assignment>();
    const assignmentsByTask = new Map<number, Assignment[]>();
    const depsByTask = new Map<number, TaskDep[]>();

    for (const assignment of assignments ?? []) {
      assignmentByKey.set(`${assignment.task_id}-${assignment.date}`, assignment);
      assignmentById.set(assignment.id, assignment);
      const taskAssignments = assignmentsByTask.get(assignment.task_id) ?? [];
      taskAssignments.push(assignment);
      assignmentsByTask.set(assignment.task_id, taskAssignments);
    }
    for (const dep of deps ?? []) {
      const taskDeps = depsByTask.get(dep.task_id) ?? [];
      taskDeps.push(dep);
      depsByTask.set(dep.task_id, taskDeps);
    }
    return {assignmentByKey, assignmentById, assignmentsByTask, depsByTask};
  }, [assignments, deps]);
}
