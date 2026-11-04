import {describe, expect, it} from 'vitest';
import {formatRolloutShift, groupRolloutBlocks} from './rolloutLegendStages';

describe('rollout stages', () => {
  it('sorts and groups without mutating cached blocks', () => {
    const blocks = Object.freeze([
      {id: 3, name: 'В', shift_days: 1}, {id: 1, name: 'А', shift_days: 0},
      {id: 2, name: 'Б', shift_days: 1},
    ]);
    expect(groupRolloutBlocks([...blocks])).toEqual([
      {shift: 0, blocks: [blocks[1]]}, {shift: 1, blocks: [blocks[2], blocks[0]]},
    ]);
    expect(blocks.map((block) => block.id)).toEqual([3, 1, 2]);
    expect(groupRolloutBlocks([])).toEqual([]);
  });
  it.each([[0, 'День 0'], [1, '+1 день'], [2, '+2 дня'], [5, '+5 дней'],
    [11, '+11 дней'], [14, '+14 дней'], [21, '+21 день'], [22, '+22 дня'],
    [111, '+111 дней'], [-1, '−1 день']])('formats %s', (days, label) => {
    expect(formatRolloutShift(Number(days))).toBe(label);
  });
});
