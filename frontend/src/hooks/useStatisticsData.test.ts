import {describe, expect, it} from 'vitest';
import dayjs from 'dayjs';
import {getStatisticsCalendarRange} from './useStatisticsData';
import {getInitialStatisticsDay, getMonthDays} from '../lib/statisticsCalendar';

describe('statistics month range', () => {
  it.each([
    ['2026-07-15', '2026-07-01', '2026-07-31'],
    ['2026-12-31', '2026-12-01', '2026-12-31'],
    ['2027-01-01', '2027-01-01', '2027-01-31'],
    ['2024-02-15', '2024-02-01', '2024-02-29'],
    ['2026-02-15', '2026-02-01', '2026-02-28'],
  ])('covers only the selected month of %s', (date, from, to) => {
    expect(getStatisticsCalendarRange(dayjs(date))).toEqual({from, to});
  });
  it('aligns weeks to Monday with blank adjacent months', () => {
    const days = getMonthDays(dayjs('2026-11-15'));
    expect(days).toHaveLength(42);
    expect(days.slice(0, 6)).toEqual(Array(6).fill(null));
    expect(days[6]?.format('YYYY-MM-DD')).toBe('2026-11-01');
    expect(days[35]?.format('YYYY-MM-DD')).toBe('2026-11-30');
    expect(days.slice(36)).toEqual(Array(6).fill(null));
    expect(getMonthDays(dayjs('2024-02-01')).filter(Boolean)).toHaveLength(29);
    expect(getMonthDays(dayjs('2024-02-01'))).toHaveLength(42);
    expect(getMonthDays(dayjs('2026-10-01'))).toHaveLength(42);
  });
});
describe('automatic day selection', () => {
  const today = dayjs('2026-10-14');
  it('selects the earliest positive day even for unsorted data', () => {
    expect(getInitialStatisticsDay(dayjs('2026-11-01'), [
      {date: '2026-12-01', count: 9}, {date: '2026-11-20', count: 2},
      {date: '2026-11-01', count: 0}, {date: '2026-11-03', count: 1},
    ], today)).toBe('2026-11-03');
  });
  it('selects first day for empty month and today for current month', () => {
    expect(getInitialStatisticsDay(dayjs('2027-01-22'), [], today)).toBe('2027-01-01');
    expect(getInitialStatisticsDay(today, [{date: '2026-10-01', count: 99}], today)).toBe('2026-10-14');
  });
});
