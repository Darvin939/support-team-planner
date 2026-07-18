import {keepPreviousData, useMutation, useQuery, useQueryClient} from '@tanstack/react-query';
import dayjs from 'dayjs';
import {apiGet, apiMutate, buildApiUrl} from '../lib/apiMutate';
import {queryKeys} from '../lib/queryKeys';
import {invalidateTaskDependencies} from '../lib/queryInvalidation';
import type {AssignmentStatus, Criticality, TaskStatus} from '../domain/types';
import {API_DATE_FORMAT} from '../lib/dateFormats';
import {MAX_PERIOD_DAYS} from './useDateRangeFilter';

export interface Task {
  id: number;
  name: string;
  description: string | null;
  criticality: Criticality;
  task_status: TaskStatus;
  segment_id: number;
  segment_name: string;
  has_active_assignments: boolean;
}

export interface Assignment {
  id: number;
  task_id: number;
  date: string;
  block: string | null;
  status: AssignmentStatus;
  user_id: number | null;
  user_name: string | null;
  comment: string | null;
  time_spent: string | null;
}

export interface TaskDep {
  task_id: number;
  dep_id: number;
  dep_name: string;
  dep_status: string;
  dep_is_deleted: boolean | number;
  dep_criticality: 'high' | 'medium' | 'low';
  dep_segment_id: number;
  dep_segment_name: string;
}

export function useTasks(teamId: number, offset: number, limit: number, search: string, showCompleted: boolean) {
  return useQuery<{ tasks: Task[]; total: number }>({
    queryKey: queryKeys.tasks.list(teamId, offset, limit, search, showCompleted),
    queryFn: () => apiGet(buildApiUrl(`/api/tasks/${teamId}`, {offset, limit, search, show_completed: showCompleted})),
    enabled: !!teamId,
  });
}

export function useAssignments(teamId: number, dateFrom: string, dateTo: string, taskIds: number[]) {
  return useQuery<Assignment[]>({
    queryKey: queryKeys.assignments.list(teamId, dateFrom, dateTo, taskIds),
    queryFn: () => apiGet(buildApiUrl(`/api/assignments/${teamId}`, {start_date: dateFrom, end_date: dateTo, task_ids: taskIds.join(',')})),
    enabled: !!teamId && taskIds.length > 0,
  });
}

export function useTaskDeps(teamId: number, taskIds: number[]) {
  return useQuery<TaskDep[]>({
    queryKey: queryKeys.taskDepsList(teamId, taskIds),
    queryFn: () => apiGet(`/api/tasks/${teamId}/deps?task_ids=${taskIds.join(',')}`),
    enabled: !!teamId && taskIds.length > 0,
  });
}

interface ActiveAssignmentLite {
  id: number;
  criticality: 'high' | 'medium' | 'low';
  status: 'new' | 'planned';
}

export function useTodayActive(teamId: number, today: string) {
  return useQuery<ActiveAssignmentLite[]>({
    queryKey: [...queryKeys.assignments.active, teamId, today, today],
    queryFn: () =>
      apiGet<{ items: ActiveAssignmentLite[] }>(`/api/active-assignments/${teamId}?start_date=${today}&end_date=${today}`).then(
        (r) => r.items
      ),
    enabled: !!teamId,
  });
}

export interface OverdueAssignment {
  id: number;
  task_id: number;
  team_id: number;
  task_name: string;
  team_name: string;
  criticality: 'high' | 'medium' | 'low';
  date: string;
  status: 'new' | 'planned';
  user_name: string | null;
  comment: string | null;
}

export function useOverdueAssignments() {
  const cutoff = dayjs().subtract(3, 'day');
  const start = cutoff.subtract(MAX_PERIOD_DAYS, 'day').format(API_DATE_FORMAT);
  const end = cutoff.format(API_DATE_FORMAT);
  return useQuery<OverdueAssignment[]>({
    queryKey: [...queryKeys.assignments.active, 0, start, end],
    queryFn: () =>
      apiGet<{ items: OverdueAssignment[] }>(`/api/active-assignments/0?start_date=${start}&end_date=${end}`).then((r) => r.items),
    refetchInterval: 5 * 60 * 1000,
  });
}

export function useTaskById(teamId: number, taskId: number | null) {
  return useQuery<Task | null>({
    queryKey: queryKeys.tasks.byId(teamId, taskId),
    queryFn: () =>
      apiGet<{ tasks: Task[] }>(buildApiUrl(`/api/tasks/${teamId}`, {task_id: taskId, show_completed: true, limit: 1})).then(
        (r) => r.tasks[0] ?? null
      ),
    enabled: !!teamId && !!taskId,
  });
}

export interface TeamBlock {
  id: number;
  name: string;
}

export function useTeamBlocks(teamId: number, segmentId?: number | null) {
  return useQuery<TeamBlock[]>({
    queryKey: queryKeys.teamBlocks(teamId, segmentId),
    queryFn: () => apiGet(`/api/teams/${teamId}/blocks${segmentId ? `?segment_id=${segmentId}` : ''}`),
    enabled: !!teamId,
  });
}

export interface BlockTemplateEntry {
  id: number;
  name: string;
  shift_days: number;
}

export interface BlockTemplateWithBlocks {
  id: number;
  name: string;
  segment_id: number;
  blocks: BlockTemplateEntry[];
}

export function useTeamTemplates(teamId: number) {
  return useQuery<BlockTemplateWithBlocks[]>({
    queryKey: queryKeys.teamTemplates(teamId),
    queryFn: () => apiGet<{ templates: BlockTemplateWithBlocks[] }>(`/api/teams/${teamId}`).then((r) => r.templates),
    enabled: !!teamId,
  });
}

export interface ActiveTaskListItem {
  id: number;
  name: string;
  task_status: string;
  criticality: string;
}

export interface DependencyGraphNode {
  id: number;
  name: string;
  description: string | null;
  task_status: string;
  criticality: string;
  segment_id: number;
  segment_name: string;
}

export interface DependencyGraphEdge {
  task_id: number;
  dep_id: number;
}

export function useDependencyGraph(teamId: number, enabled: boolean, taskId?: number) {
  return useQuery<{ nodes: DependencyGraphNode[]; edges: DependencyGraphEdge[] }>({
    queryKey: queryKeys.dependencyGraphFor(teamId, taskId),
    queryFn: () => apiGet(`/api/tasks/${teamId}/dependency-graph${taskId ? `?task_id=${taskId}` : ''}`),
    enabled: !!teamId && enabled,
  });
}

/** Добавление/удаление одной связи зависимости прямо с графа (POST/DELETE /api/task-dependency),
 * без пересохранения всей задачи через /api/task. */
export function useAddTaskDependency() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (vars: { task_id: number; depends_on_task_id: number }) =>
      apiMutate('/api/task-dependency', 'POST', vars),
    onSuccess: () => {
      invalidateTaskDependencies(queryClient);
    },
  });
}

export function useRemoveTaskDependency() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (vars: { task_id: number; depends_on_task_id: number }) =>
      apiMutate('/api/task-dependency', 'DELETE', vars),
    onSuccess: () => {
      invalidateTaskDependencies(queryClient);
    },
  });
}

export function useActiveTasksList(teamId: number, search: string, includeIds: number[]) {
  const includeIdsKey = [...includeIds].sort((a, b) => a - b).join(',');
  return useQuery<ActiveTaskListItem[]>({
    queryKey: queryKeys.activeTasks(teamId, search, includeIdsKey),
    queryFn: () =>
      apiGet(
        `/api/tasks/${teamId}/active-list?search=${encodeURIComponent(search)}` +
          (includeIdsKey ? `&include_ids=${includeIdsKey}` : '')
      ),
    enabled: !!teamId,
    placeholderData: keepPreviousData,
  });
}
