// @vitest-environment jsdom
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {act, cleanup, renderHook} from '@testing-library/react';
import type {ReactNode} from 'react';
import {afterEach, describe, expect, it, vi} from 'vitest';
import {useBulkSaveAssignmentsMutation, useDeleteAssignmentMutation, useSaveAssignmentMutation} from './useAssignmentMutations';
import {apiMutate} from '../lib/apiMutate';
import {queryKeys} from '../lib/queryKeys';

vi.mock('../lib/apiMutate', () => ({apiMutate: vi.fn()}));
vi.mock('antd', () => ({message: {success: vi.fn(), error: vi.fn()}}));
afterEach(() => {cleanup(); vi.clearAllMocks();});

function setup() {
  const client = new QueryClient({defaultOptions: {queries: {retry: false}, mutations: {retry: false}}});
  const invalidate = vi.spyOn(client, 'invalidateQueries').mockResolvedValue();
  const wrapper = ({children}: {children: ReactNode}) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  return {client, invalidate, wrapper};
}

describe('assignment mutation results', () => {
  it('preserves every bulk suggestion and invalidates task readiness', async () => {
    const {client, invalidate, wrapper} = setup();
    const response = {success: true, task_completion_suggestions: [
      {task_id: 1, task_name: 'First'}, {task_id: 2, task_name: 'Second'},
    ]};
    vi.mocked(apiMutate).mockResolvedValue(response);
    const onSuccess = vi.fn();
    const {result} = renderHook(() => useBulkSaveAssignmentsMutation({onSuccess}), {wrapper});
    await act(async () => {await result.current.mutateAsync({assignments: []});});
    expect(onSuccess).toHaveBeenCalledWith({...response, saved: 0});
    expect(invalidate).toHaveBeenCalledWith({queryKey: queryKeys.tasks.all});
    client.clear();
  });

  it('invalidates readiness on a save and a delete even without includeTasks', async () => {
    const {client, invalidate, wrapper} = setup();
    vi.mocked(apiMutate).mockResolvedValue({success: true});
    const {result} = renderHook(() => ({save: useSaveAssignmentMutation(), remove: useDeleteAssignmentMutation()}), {wrapper});
    await act(async () => {await result.current.save.mutateAsync({task_id: 1, date: '2026-11-04',
      block: 'A', status: 'success', user_id: null, comment: null, time_spent: null});});
    expect(invalidate).toHaveBeenCalledWith({queryKey: queryKeys.tasks.all});
    invalidate.mockClear();
    await act(async () => {await result.current.remove.mutateAsync(1);});
    expect(invalidate).toHaveBeenCalledWith({queryKey: queryKeys.tasks.all});
    client.clear();
  });
});
