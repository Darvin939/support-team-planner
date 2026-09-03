import dayjs from 'dayjs';
import type {Assignment} from '../../domain/types';
import {apiGet} from '../../lib/apiMutate';
import {DISPLAY_DATE_FORMAT} from '../../lib/dateFormats';

export function getSuccessfulAssignmentHistory(teamId: number, taskId: number): Promise<Assignment[]> {
  return apiGet<Assignment[]>(`/api/assignments/${teamId}/task/${taskId}/successful-history`);
}

interface LatestBlock {
  name: string;
  date: string;
  order: number;
}

export function buildSuccessfulAssignmentsText(taskName: string, assignments: Assignment[]): string | null {
  const latestByBlock = new Map<string, LatestBlock>();
  let order = 0;

  assignments.forEach((assignment) => {
    if (assignment.status !== 'success') return;
    for (const value of (assignment.block ?? '').split(',')) {
      const block = value.trim();
      if (!block) continue;

      const current = latestByBlock.get(block);
      if (!current || assignment.date >= current.date) {
        latestByBlock.set(block, {name: block, date: assignment.date, order});
      }
      order += 1;
    }
  });

  if (latestByBlock.size === 0) return null;

  const groupedByDate = new Map<string, string[]>();
  const latestBlocks = [...latestByBlock.values()].sort(
    (left, right) => left.date.localeCompare(right.date) || left.order - right.order,
  );
  latestBlocks.forEach(({name, date}) => {
    const blocks = groupedByDate.get(date) ?? [];
    blocks.push(name);
    groupedByDate.set(date, blocks);
  });

  const lines = [...groupedByDate.entries()].map(
    ([date, blocks]) => `${blocks.join(', ')} - ${dayjs(date).format(DISPLAY_DATE_FORMAT)}`,
  );
  return [taskName, ...lines].join('\n');
}
