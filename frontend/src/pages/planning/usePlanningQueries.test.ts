import {describe, expect, it} from 'vitest';
import {stableTaskIdsForPlanningQueries} from './usePlanningQueries';

describe('stableTaskIdsForPlanningQueries', () => {
  it('возвращает одинаковый порядок ID для одного набора задач после перестановки строк', () => {
    const originalOrder = [17, 3, 9];
    const reordered = [9, 17, 3];

    expect(stableTaskIdsForPlanningQueries(originalOrder)).toEqual([3, 9, 17]);
    expect(stableTaskIdsForPlanningQueries(reordered)).toEqual([3, 9, 17]);
    expect(originalOrder).toEqual([17, 3, 9]);
  });
});
