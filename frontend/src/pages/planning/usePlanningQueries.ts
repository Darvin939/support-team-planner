import {useMemo} from 'react';
import {useAssignments, useTaskDeps, useTasks, useTodayActive,} from '../../hooks/usePlanningData';

export function stableTaskIdsForPlanningQueries(taskIds: number[]): number[] {
  // Query keys represent a set of IDs; task row order must not start redundant dependent requests.
  return [...taskIds].sort((left, right) => left - right);
}

export function usePlanningQueries(options: {
  teamId: number;
  offset: number;
  pageSize: number;
  search: string;
  showCompleted: boolean;
  dateFrom: string;
  dateTo: string;
  today: string;
  depJumpTaskId: number | null;
  freezeDaysPending: boolean;
  freezeDaysError: boolean;
}) {
  const tasksQuery = useTasks(
    options.teamId, options.offset, options.pageSize, options.search, options.showCompleted,
  );
  const taskIds = useMemo(() => tasksQuery.data?.tasks.map((task) => task.id) ?? [], [tasksQuery.data]);
  const queryTaskIds = useMemo(() => stableTaskIdsForPlanningQueries(taskIds), [taskIds]);
  const depsTaskIds = useMemo(
    () => options.depJumpTaskId && !queryTaskIds.includes(options.depJumpTaskId)
      ? [...queryTaskIds, options.depJumpTaskId]
      : queryTaskIds,
    [queryTaskIds, options.depJumpTaskId],
  );
  const assignmentsQuery = useAssignments(options.teamId, options.dateFrom, options.dateTo, queryTaskIds);
  const depsQuery = useTaskDeps(options.teamId, depsTaskIds);
  const todayActiveQuery = useTodayActive(options.teamId, options.today);
  const hasTasks = taskIds.length > 0;
  const error = tasksQuery.isError || options.freezeDaysError ||
    (hasTasks && (assignmentsQuery.isError || depsQuery.isError));
  const ready = !tasksQuery.isPending && !options.freezeDaysPending && !error &&
    (!hasTasks || (!assignmentsQuery.isPending && !depsQuery.isPending));

  return {
    taskData: tasksQuery.data,
    taskIds,
    assignments: assignmentsQuery.data,
    deps: depsQuery.data,
    todayActive: todayActiveQuery.data,
    planningDataError: error,
    planningDataReady: ready,
  };
}
