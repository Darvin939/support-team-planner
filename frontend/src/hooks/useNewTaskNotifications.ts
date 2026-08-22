import {useMutation, useQuery, useQueryClient} from '@tanstack/react-query';
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
  });
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
