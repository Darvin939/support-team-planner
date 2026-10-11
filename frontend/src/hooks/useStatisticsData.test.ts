import {describe, expect, it} from 'vitest';
import dayjs from 'dayjs';
import {getStatisticsCalendarRange} from './useStatisticsData';

describe('getStatisticsCalendarRange', () => {
  it('covers all six rows of both panels including neighboring-month dates', () => {
    expect(getStatisticsCalendarRange(dayjs('2026-07-15'))).toEqual({
      from: '2026-06-29',
      to: '2026-09-06',
    });
  });

  it('updates the full grid range when the first panel changes', () => {
    expect(getStatisticsCalendarRange(dayjs('2026-08-01'))).toEqual({
      from: '2026-07-27',
      to: '2026-10-11',
    });
  });
});
