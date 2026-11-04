import type {BlockTemplateEntry} from '../../domain/types';

export function formatRolloutShift(days: number): string {
  if (days === 0) return 'День 0';
  const value = Math.abs(days);
  const lastTwo = value % 100;
  const last = value % 10;
  const word = lastTwo >= 11 && lastTwo <= 14 ? 'дней'
    : last === 1 ? 'день' : last >= 2 && last <= 4 ? 'дня' : 'дней';
  return `${days > 0 ? '+' : '−'}${value} ${word}`;
}

export function groupRolloutBlocks(blocks: BlockTemplateEntry[]) {
  const groups = new Map<number, BlockTemplateEntry[]>();
  for (const block of [...blocks].sort((a, b) => a.shift_days - b.shift_days || a.name.localeCompare(b.name, 'ru'))) {
    const group = groups.get(block.shift_days) ?? [];
    group.push(block);
    groups.set(block.shift_days, group);
  }
  return Array.from(groups, ([shift, entries]) => ({shift, blocks: entries}));
}
