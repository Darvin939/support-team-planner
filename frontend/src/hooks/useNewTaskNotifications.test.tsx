// @vitest-environment jsdom

import {afterEach, describe, expect, it, vi} from 'vitest';
import {act, cleanup, renderHook, waitFor} from '@testing-library/react';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import type {ReactNode} from 'react';
import {queryKeys} from '../lib/queryKeys';
import {useMarkNewTaskItemsSeen} from './useNewTaskNotifications';

const apiMutate = vi.hoisted(() => vi.fn());
vi.mock('../lib/apiMutate', () => ({
  apiGet: vi.fn(),
  apiMutate,
  buildApiUrl: (path: string) => path,
}));

const page = {
  items: [{task_id: 10, team_id: 1, task_name: 'Работа', team_name: 'Команда', criticality: 'high',
    task_status: 'new', changed_at: '2026-09-01 10:00:00', author_name: 'Автор'}],
  total: 1,
  watermark: {changed_at: '2026-09-01 10:00:00', history_id: 1},
};

describe('useMarkNewTaskItemsSeen', () => {
  afterEach(() => { cleanup(); apiMutate.mockReset(); });

  it('optimistic удаляет работу и восстанавливает кэш при ошибке', async () => {
    let rejectRequest!: (error: Error) => void;
    apiMutate.mockImplementationOnce(() => new Promise((_resolve, reject) => { rejectRequest = reject; }));
    const client = new QueryClient({defaultOptions: {queries: {retry: false}, mutations: {retry: false}}});
    client.setQueryData(queryKeys.newTaskNotifications.preview, page);
    const wrapper = ({children}: {children: ReactNode}) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
    const {result} = renderHook(() => useMarkNewTaskItemsSeen(), {wrapper});

    act(() => result.current.mutate([10]));
    await waitFor(() => expect(client.getQueryData(queryKeys.newTaskNotifications.preview)).toMatchObject({items: [], total: 0}));
    act(() => rejectRequest(new Error('network')));
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(client.getQueryData(queryKeys.newTaskNotifications.preview)).toEqual(page);
  });
});
