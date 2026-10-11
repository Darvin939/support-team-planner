import {describe, expect, it} from 'vitest';
import {queryKeys} from './queryKeys';

describe('queryKeys', () => {
  it('normalizes set-like team IDs without mutating the caller', () => {
    const ids = [7, 2];
    expect(queryKeys.assignments.activeList('2026-01-01', '2026-01-02', ids, 0, 20))
      .toEqual(['active-assignments', '2026-01-01', '2026-01-02', [2, 7], 0, 20]);
    expect(ids).toEqual([7, 2]);
  });

  it('keeps journal queries under the journal root and separates page sizes', () => {
    const key = queryKeys.journal.list(3, 20, 50, {search: ''});
    expect(key.slice(0, 1)).toEqual(queryKeys.journal.all);
    expect(key).toEqual(['journal', 3, 20, 50, {search: ''}]);
  });

  it('separates calendar count ranges and normalizes their team IDs', () => {
    expect(queryKeys.assignments.dateCounts('2026-07-01', '2026-08-31', [7, 2]))
      .toEqual(['active-assignment-counts', '2026-07-01', '2026-08-31', [2, 7]]);
    expect(queryKeys.assignments.dateCounts('2026-08-01', '2026-09-30', [7, 2]))
      .not.toEqual(queryKeys.assignments.dateCounts('2026-07-01', '2026-08-31', [7, 2]));
  });
});
