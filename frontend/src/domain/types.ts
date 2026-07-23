export type Criticality = 'high' | 'medium' | 'low';
export type TaskStatus = 'new' | 'ready' | 'in_progress' | 'done' | 'cancelled';
export type AssignmentStatus = 'new' | 'planned' | 'rollback' | 'success' | 'cancelled';
export type UserRole = 'admin' | 'editor' | 'user';

export interface Task {
  id: number;
  name: string;
  description: string | null;
  criticality: Criticality;
  task_status: TaskStatus;
  segment_id: number;
  segment_name: string;
  completed_at: string | null;
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
  dep_criticality: Criticality;
  dep_segment_id: number;
  dep_segment_name: string;
}

export interface User {
  id: number;
  last_name: string | null;
  first_name: string;
  middle_name: string | null;
  role: UserRole;
  login: string | null;
  is_assignee: boolean;
  is_protected: boolean;
  team_ids: number[];
}

export interface Team {
  id: number;
  name: string;
  templates?: Array<{id: number; name: string}>;
}

export interface Block {
  id: number;
  name: string;
}

export interface BlockTemplateEntry extends Block {
  shift_days: number;
}

export interface BlockTemplate {
  id: number;
  name: string;
  segment_id: number;
  blocks: BlockTemplateEntry[];
}

export interface Segment {
  id: number;
  name: string;
}

export const ASSIGNMENT_STATUS_OPTIONS = [
  {value: 'new', label: 'Новый'},
  {value: 'planned', label: 'Запланировано'},
  {value: 'rollback', label: 'Откат'},
  {value: 'success', label: 'Успешно'},
  {value: 'cancelled', label: 'Отменено'},
] satisfies Array<{value: AssignmentStatus; label: string}>;

export const TASK_STATUS_OPTIONS = [
  {value: 'new', label: 'Новый'},
  {value: 'ready', label: 'К планированию'},
  {value: 'in_progress', label: 'В работе'},
  {value: 'done', label: 'Выполнено'},
  {value: 'cancelled', label: 'Отменено'},
] satisfies Array<{value: TaskStatus; label: string}>;

export const CRITICALITY_OPTIONS = [
  {value: 'low', label: 'Низкая'},
  {value: 'medium', label: 'Средняя'},
  {value: 'high', label: 'Высокая'},
] satisfies Array<{value: Criticality; label: string}>;

export const ROLE_OPTIONS = [
  {value: 'user', label: 'Пользователь'},
  {value: 'editor', label: 'Редактор'},
  {value: 'admin', label: 'Администратор'},
] satisfies Array<{value: UserRole; label: string}>;

export const ASSIGNMENT_STATUS_LABELS: Record<string, string> = {
  new: 'Новый', planned: 'Запланировано', rollback: 'Откат', success: 'Успешно', cancelled: 'Отменено',
};

export const CRITICALITY_LABELS: Record<string, string> = {
  high: 'Высокая', medium: 'Средняя', low: 'Низкая',
};

export const TASK_STATUS_LABELS: Record<string, string> = {
  new: 'Новый', ready: 'К планированию', in_progress: 'В работе', done: 'Выполнено', cancelled: 'Отменено',
};
