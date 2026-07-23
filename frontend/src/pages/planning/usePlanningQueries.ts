import {useMemo} from 'react';
import {
  useAssignments,
  useTaskDeps,
  useTasks,
  useTodayActive,
} from '../../hooks/usePlanningData';

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
  const depsTaskIds = useMemo(
    () => options.depJumpTaskId && !taskIds.includes(options.depJumpTaskId)
      ? [...taskIds, options.depJumpTaskId]
      : taskIds,
    [taskIds, options.depJumpTaskId],
  );
  const assignmentsQuery = useAssignments(options.teamId, options.dateFrom, options.dateTo, taskIds);
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
