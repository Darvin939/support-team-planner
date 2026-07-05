import {useQuery} from '@tanstack/react-query';

export interface Task {
  id: number;
  name: string;
  description: string | null;
  criticality: 'high' | 'medium' | 'low';
  task_status: 'new' | 'ready' | 'in_progress' | 'done' | 'cancelled';
}

export interface Assignment {
  id: number;
  task_id: number;
  date: string;
  block: string | null;
  status: 'new' | 'planned' | 'rollback' | 'success';
  employee_id: number | null;
  employee_name: string | null;
  comment: string | null;
  is_psi: boolean;
  time_spent: string | null;
}

export interface TaskDep {
  task_id: number;
  dep_id: number;
  dep_name: string;
  dep_status: string;
  dep_is_deleted: boolean | number;
}

async function getJson<T>(url: string): Promise<T> {
  const r = await fetch(url, { credentials: 'same-origin' });
  if (!r.ok) throw new Error(`GET ${url} -> ${r.status}`);
  return r.json();
}

export function useTasks(teamId: number, offset: number, limit: number, search: string, showCompleted: boolean) {
  return useQuery<{ tasks: Task[]; total: number }>({
    queryKey: ['tasks', teamId, offset, limit, search, showCompleted],
    queryFn: () => getJson(`/api/tasks/${teamId}?offset=${offset}&limit=${limit}&search=${encodeURIComponent(search)}&show_completed=${showCompleted}`),
    enabled: !!teamId,
  });
}

export function useAssignments(teamId: number, dateFrom: string, dateTo: string, taskIds: number[]) {
  return useQuery<Assignment[]>({
    queryKey: ['assignments', teamId, dateFrom, dateTo, taskIds],
    queryFn: () => getJson(`/api/assignments/${teamId}?start_date=${dateFrom}&end_date=${dateTo}&task_ids=${taskIds.join(',')}`),
    enabled: !!teamId && taskIds.length > 0,
  });
}

export function useTaskDeps(teamId: number, taskIds: number[]) {
  return useQuery<TaskDep[]>({
    queryKey: ['task-deps', teamId, taskIds],
    queryFn: () => getJson(`/api/tasks/${teamId}/deps?task_ids=${taskIds.join(',')}`),
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
    queryKey: ['active-assignments', teamId, today, today],
    queryFn: () => getJson(`/api/active-assignments/${teamId}?start_date=${today}&end_date=${today}`),
    enabled: !!teamId,
  });
}

export interface TeamBlock {
  id: number;
  name: string;
}

export function useTeamBlocks(teamId: number) {
  return useQuery<TeamBlock[]>({
    queryKey: ['team-blocks', teamId],
    queryFn: () => getJson(`/api/teams/${teamId}/blocks`),
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
  blocks: BlockTemplateEntry[];
}

export function useTeamTemplates(teamId: number) {
  return useQuery<BlockTemplateWithBlocks[]>({
    queryKey: ['team-templates', teamId],
    queryFn: () => getJson<{ templates: BlockTemplateWithBlocks[] }>(`/api/teams/${teamId}`).then((r) => r.templates),
    enabled: !!teamId,
  });
}

export interface ActiveTaskListItem {
  id: number;
  name: string;
  task_status: string;
  criticality: string;
}

export function useActiveTasksList(teamId: number) {
  return useQuery<ActiveTaskListItem[]>({
    queryKey: ['active-tasks-list', teamId],
    queryFn: () => getJson(`/api/tasks/${teamId}/active-list`),
    enabled: !!teamId,
  });
}
