export const HISTORY_FIELD_LABELS: Record<string, string> = {
  name: 'Название', description: 'Описание', criticality: 'Критичность', priority: 'Приоритет', task_status: 'Статус',
  date: 'Дата', block: 'Блок', status: 'Статус',
  // employee_id — старое имя поля, всё ещё встречается в исторических записях, созданных до
  // переименования employees -> users; user_id — новые записи. Оба должны отображаться одинаково.
  employee_id: 'Исполнитель', user_id: 'Исполнитель',
  comment: 'Комментарий', is_psi: 'ПСИ', time_spent: 'Время выполнения', is_deleted: 'Удаление',
};

export const CRITICALITY_LABELS: Record<string, string> = { high: 'Высокая', medium: 'Средняя', low: 'Низкая' };

export const TASK_STATUS_LABELS: Record<string, string> = {
  new: 'Новый', ready: 'К планированию', in_progress: 'В работе', done: 'Выполнено', cancelled: 'Отменено',
};

export const ASSIGNMENT_STATUS_LABELS: Record<string, string> = {
  new: 'Новый', planned: 'Запланировано', rollback: 'Откат', success: 'Успешно', cancelled: 'Отменено',
};

export interface HistoryEntry {
  id: number;
  entity?: 'task' | 'assignment';
  action?: string;
  field_name: string;
  old_value: string | null;
  new_value: string | null;
  date: string | null;
  changed_at: string;
  changed_by_last_name?: string | null;
  changed_by_first_name?: string | null;
  changed_by_middle_name?: string | null;
  task_name?: string;
  task_is_deleted?: boolean | number;
}

export function formatChangedBy(entry: HistoryEntry): string {
  if (!entry.changed_by_last_name && !entry.changed_by_first_name) return 'Система';
  if (!entry.changed_by_last_name) return entry.changed_by_first_name!;
  if (!entry.changed_by_first_name) return entry.changed_by_last_name;
  const initials = `${entry.changed_by_first_name.charAt(0)}.${entry.changed_by_middle_name ? entry.changed_by_middle_name.charAt(0) + '.' : ''}`;
  return `${entry.changed_by_last_name} ${initials}`;
}

export function formatHistoryValue(field: string, value: string | null, getUserName: (id: string) => string): string {
  if (field === 'is_deleted') return value === '1' ? 'Да' : 'Нет';
  if (value === null || value === undefined || value === '') return '—';
  if (field === 'criticality') return CRITICALITY_LABELS[value] || value;
  if (field === 'task_status') return TASK_STATUS_LABELS[value] || value;
  if (field === 'status') return ASSIGNMENT_STATUS_LABELS[value] || value;
  if (field === 'employee_id' || field === 'user_id') return getUserName(value);
  if (field === 'is_psi') return value === '1' ? 'Да' : 'Нет';
  return value;
}

/** Собирает текст одной строки истории (без времени/автора) — используется и в журнале, и в панели истории. */
export function formatHistoryText(
  entry: HistoryEntry,
  getUserName: (id: string) => string,
  showAssignmentContext: boolean,
): string {
  const isAssignmentRow = entry.entity === 'assignment';

  if (entry.field_name === 'is_deleted' && entry.new_value === '1') {
    return isAssignmentRow ? `Назначение на ${entry.date} удалено` : 'Задача удалена';
  }
  if (entry.action === 'create') {
    return isAssignmentRow ? `Назначение на ${entry.date} создано` : 'Задача создана';
  }
  if (entry.action === 'delete') {
    return isAssignmentRow ? `Назначение на ${entry.date} удалено` : 'Задача удалена';
  }
  const label = HISTORY_FIELD_LABELS[entry.field_name] || entry.field_name;
  const oldV = formatHistoryValue(entry.field_name, entry.old_value, getUserName);
  const newV = formatHistoryValue(entry.field_name, entry.new_value, getUserName);
  const changeText = `${label}: ${oldV} ➜ ${newV}`;
  return showAssignmentContext && isAssignmentRow ? `Назначение на ${entry.date} — ${changeText}` : changeText;
}
