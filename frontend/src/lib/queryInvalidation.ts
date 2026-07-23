import type {QueryClient, QueryKey} from '@tanstack/react-query';
import {queryKeys} from './queryKeys';

export function invalidateAssignmentData(queryClient: QueryClient, includeTasks = false) {
  return Promise.all([
    queryClient.invalidateQueries({queryKey: queryKeys.assignments.all}),
    queryClient.invalidateQueries({queryKey: queryKeys.assignments.active}),
    ...(includeTasks ? [queryClient.invalidateQueries({queryKey: queryKeys.tasks.all})] : []),
  ]);
}

export function invalidateTaskDependencies(queryClient: QueryClient) {
  return Promise.all([
    queryClient.invalidateQueries({queryKey: queryKeys.dependencyGraph}),
    queryClient.invalidateQueries({queryKey: queryKeys.taskDeps}),
  ]);
}

export function invalidateTaskData(
  queryClient: QueryClient,
  options: {activeAssignments?: boolean; dependencies?: boolean} = {},
) {
  return Promise.all([
    queryClient.invalidateQueries({queryKey: queryKeys.tasks.all}),
    ...(options.activeAssignments
      ? [queryClient.invalidateQueries({queryKey: queryKeys.assignments.active})]
      : []),
    ...(options.dependencies
      ? [
          queryClient.invalidateQueries({queryKey: queryKeys.taskDeps}),
          queryClient.invalidateQueries({queryKey: queryKeys.dependencyGraph}),
        ]
      : []),
  ]);
}

export function invalidateSettingsData(queryClient: QueryClient, queryKey: QueryKey) {
  return queryClient.invalidateQueries({queryKey});
}
