import dayjs, {type Dayjs} from 'dayjs';
import {API_DATE_FORMAT} from './dateFormats';

export function getMonthDays(month: Dayjs): Array<Dayjs | null> {
  const first = month.startOf('month');
  const offset = (first.day() + 6) % 7;
  // Keep the following content at the same position when navigating months.
  const length = 42;
  return Array.from({length}, (_, index) => {
    const day = index - offset + 1;
    return day > 0 && day <= month.daysInMonth() ? first.date(day) : null;
  });
}

export function getInitialStatisticsDay(month: Dayjs, counts: Array<{date: string; count: number}>, today = dayjs()): string {
  if (month.isSame(today, 'month')) return today.format(API_DATE_FORMAT);
  const prefix = month.format('YYYY-MM');
  return counts.filter(item => item.count > 0 && item.date.startsWith(`${prefix}-`))
    .map(item => item.date).sort()[0] ?? month.startOf('month').format(API_DATE_FORMAT);
}
