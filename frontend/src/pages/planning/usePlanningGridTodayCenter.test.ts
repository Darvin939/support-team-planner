import {describe, expect, it} from 'vitest';
import {createPlanningGridViewKey} from './usePlanningGridTodayCenter';

const baseOptions = {
  teamId: 1,
  dateFrom: '2026-10-01',
  dateTo: '2026-10-31',
  search: '',
  showCompleted: false,
  page: 1,
  pageSize: 20,
  criticalities: [],
  assignmentStatuses: [],
  taskStatuses: [],
  psiStatuses: [],
  segmentIds: [],
  taskIds: [1, 2],
};

describe('createPlanningGridViewKey PSI filter', () => {
  it('changes the view key when selected PSI statuses change', () => {
    const allStatusesKey = createPlanningGridViewKey(baseOptions);
    const requiredKey = createPlanningGridViewKey({...baseOptions, psiStatuses: ['required']});

    expect(requiredKey).not.toBe(allStatusesKey);
  });
});
