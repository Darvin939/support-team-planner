import type {QueryClient} from '@tanstack/react-query';
import {queryKeys} from './queryKeys';

export function invalidateAssignmentData(queryClient: QueryClient, includeTasks = false) {
  queryClient.invalidateQueries({queryKey: queryKeys.assignments.all});
  queryClient.invalidateQueries({queryKey: queryKeys.assignments.active});
  if (includeTasks) queryClient.invalidateQueries({queryKey: queryKeys.tasks.all});
}

export function invalidateTaskDependencies(queryClient: QueryClient) {
  queryClient.invalidateQueries({queryKey: queryKeys.dependencyGraph});
  queryClient.invalidateQueries({queryKey: queryKeys.taskDeps});
}
