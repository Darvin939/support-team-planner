import dayjs from 'dayjs';
import type {AssignmentTimelineItem} from '../../hooks/usePlanningData';

export function splitAssignmentBlocks(block: string | null): string[] {
  return (block ?? '').split(',').map((value) => value.trim()).filter(Boolean);
}

export function buildAssignmentTimelineDates(assignments: Pick<AssignmentTimelineItem, 'date'>[]): string[] {
  if (assignments.length === 0) return [];
  const dates = assignments.map(({date}) => date).sort();
  const first = dayjs(dates[0]);
  const last = dayjs(dates[dates.length - 1]);
  const result: string[] = [];
  let current = first;
  while (current.isBefore(last, 'day') || current.isSame(last, 'day')) {
    result.push(current.format('YYYY-MM-DD'));
    current = current.add(1, 'day');
  }
  return result;
}
