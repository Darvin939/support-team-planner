import {describe, expect, it, vi} from 'vitest';
import type {QueryClient} from '@tanstack/react-query';
import {invalidateAssignmentData, invalidateSettingsData, invalidateTaskData, invalidateTaskDependencies} from './queryInvalidation';
import {queryKeys} from './queryKeys';

function client() {
  return {invalidateQueries: vi.fn().mockResolvedValue(undefined)} as unknown as QueryClient;
}

describe('query invalidation policies', () => {
  it.each([queryKeys.blockTemplates, queryKeys.teams])('refreshes task configuration after directory changes %s', async (...key) => {
    const queryClient = client();
    await invalidateSettingsData(queryClient, key);
    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({queryKey: ['team-templates']});
    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({queryKey: ['team-blocks']});
    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({queryKey: queryKeys.tasks.all});
  });
  it('invalidates task roots and optional consumers', async () => {
    const queryClient = client();
    await invalidateTaskData(queryClient, {activeAssignments: true, dependencies: true});
    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({queryKey: queryKeys.tasks.all});
    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({queryKey: queryKeys.assignments.active});
    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({queryKey: queryKeys.taskDeps});
    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({queryKey: queryKeys.dependencyGraph});
  });

  it('invalidates assignment and dependency families', async () => {
    const queryClient = client();
    await invalidateAssignmentData(queryClient, true);
    await invalidateTaskDependencies(queryClient);
    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({queryKey: queryKeys.assignments.all});
    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({queryKey: queryKeys.tasks.all});
    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({queryKey: queryKeys.taskDeps});
  });
});
