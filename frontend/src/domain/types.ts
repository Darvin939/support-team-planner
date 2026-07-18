export type Criticality = 'high' | 'medium' | 'low';
export type TaskStatus = 'new' | 'ready' | 'in_progress' | 'done' | 'cancelled';
export type AssignmentStatus = 'new' | 'planned' | 'rollback' | 'success' | 'cancelled';

export const ASSIGNMENT_STATUS_LABELS: Record<string, string> = {
  new: 'Новый', planned: 'Запланировано', rollback: 'Откат', success: 'Успешно', cancelled: 'Отменено',
};

export const CRITICALITY_LABELS: Record<string, string> = {
  high: 'Высокая', medium: 'Средняя', low: 'Низкая',
};

export const TASK_STATUS_LABELS: Record<string, string> = {
  new: 'Новый', ready: 'К планированию', in_progress: 'В работе', done: 'Выполнено', cancelled: 'Отменено',
};
