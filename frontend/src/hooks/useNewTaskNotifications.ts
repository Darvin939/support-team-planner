import {useCallback, useEffect, useRef} from 'react';
import {useMutation, useQuery, useQueryClient} from '@tanstack/react-query';
import {message} from 'antd';
import {apiGet, apiMutate, buildApiUrl} from '../lib/apiMutate';
import {queryKeys} from '../lib/queryKeys';

export interface NotificationCursor {
  changed_at: string;
  history_id: number;
}

export interface NewTaskNotification {
  task_id: number;
  team_id: number;
  task_name: string;
  team_name: string;
  criticality: 'low' | 'medium' | 'high';
  task_status: 'new' | 'done' | 'cancelled';
  changed_at: string;
  author_name: string | null;
}

export interface NewTaskNotificationsPage {
  items: NewTaskNotification[];
  total: number;
  watermark: NotificationCursor;
}

export function useNewTaskNotificationsPreview() {
  return useQuery<NewTaskNotificationsPage>({
    queryKey: queryKeys.newTaskNotifications.preview,
    queryFn: () => apiGet('/api/notifications/new-tasks/preview'),
    refetchInterval: 5 * 60 * 1000,
    refetchOnWindowFocus: true,
  });
}

type NotificationCacheSnapshot = Array<[readonly unknown[], NewTaskNotificationsPage | undefined]>;

export function useMarkNewTaskItemsSeen() {
  const queryClient = useQueryClient();
  return useMutation<{success: boolean; marked: number}, Error, number[], {snapshot: NotificationCacheSnapshot}>({
    mutationFn: (taskIds) => apiMutate('/api/notifications/new-tasks/seen-items', 'POST', {task_ids: taskIds}),
    onMutate: async (taskIds) => {
      await queryClient.cancelQueries({queryKey: queryKeys.newTaskNotifications.all});
      const snapshot = queryClient.getQueriesData<NewTaskNotificationsPage>({queryKey: queryKeys.newTaskNotifications.all});
      const ids = new Set(taskIds);
      queryClient.setQueriesData<NewTaskNotificationsPage>({queryKey: queryKeys.newTaskNotifications.all}, (data) => {
        if (!data) return data;
        const items = data.items.filter((item) => !ids.has(item.task_id));
        return {...data, items, total: Math.max(0, data.total - (data.items.length - items.length))};
      });
      return {snapshot};
    },
    onError: (_error, _taskIds, context) => {
      context?.snapshot.forEach(([queryKey, data]) => queryClient.setQueryData(queryKey, data));
      message.error('Не удалось отметить работы просмотренными');
    },
    onSuccess: () => queryClient.invalidateQueries({queryKey: queryKeys.newTaskNotifications.all}),
  });
}

export function useNewTaskViewQueue() {
  const mutation = useMarkNewTaskItemsSeen();
  const mutateRef = useRef(mutation.mutate);
  mutateRef.current = mutation.mutate;
  const pending = useRef(new Set<number>());
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const flush = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
    const ids = [...pending.current];
    pending.current.clear();
    if (ids.length) mutateRef.current(ids);
  }, []);
  const enqueue = useCallback((taskIds: number[]) => {
    taskIds.forEach((id) => pending.current.add(id));
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(flush, 500);
  }, [flush]);
  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
    const ids = [...pending.current];
    pending.current.clear();
    if (ids.length) mutateRef.current(ids);
  }, [flush]);
  return {enqueue, isPending: mutation.isPending};
}

export function useNewTaskNotificationsPage(offset: number, limit: number, watermark?: NotificationCursor) {
  return useQuery<NewTaskNotificationsPage>({
    queryKey: queryKeys.newTaskNotifications.list(
      offset, limit, watermark?.changed_at ?? '', watermark?.history_id ?? 0,
    ),
    queryFn: () => apiGet(buildApiUrl('/api/notifications/new-tasks', {
      offset,
      limit,
      watermark_at: watermark?.changed_at,
      watermark_id: watermark?.history_id,
    })),
    enabled: !!watermark,
  });
}

export function useMarkNewTasksSeen() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (watermark: NotificationCursor) =>
      apiMutate('/api/notifications/new-tasks/seen', 'POST', {watermark}),
    onSuccess: () => queryClient.invalidateQueries({queryKey: queryKeys.newTaskNotifications.all}),
  });
}
