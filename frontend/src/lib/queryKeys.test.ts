import {describe, expect, it} from 'vitest';
import {queryKeys} from './queryKeys';

describe('queryKeys', () => {
  it('normalizes set-like team IDs without mutating the caller', () => {
    const ids = [7, 2];
    expect(queryKeys.assignments.activeList('2026-01-01', '2026-01-02', ids, 0, 20))
      .toEqual(['active-assignments', '2026-01-01', '2026-01-02', [2, 7], 0, 20]);
    expect(ids).toEqual([7, 2]);
  });

  it('keeps journal queries under the journal root', () => {
    expect(queryKeys.journal.list(3, 20, {search: ''}).slice(0, 1))
      .toEqual(queryKeys.journal.all);
  });
});
