import {useState} from 'react';
import dayjs, {type Dayjs} from 'dayjs';
import {API_DATE_FORMAT} from '../lib/dateFormats';

const STORAGE_DATE_FROM = 'filterDateFrom';
const STORAGE_DATE_TO = 'filterDateTo';
export const MAX_PERIOD_DAYS = 60;

/**
 * Shared date-range filter state (Planning + Statistics): reads/writes the
 * same `filterDateFrom`/`filterDateTo` localStorage keys so the selected
 * period stays in sync across both pages, and clamps to a 60-day max span.
 */
export function useDateRangeFilter(defaultRange: () => [Dayjs, Dayjs]) {
  const [range, setRange] = useState<[Dayjs, Dayjs]>(() => {
    const from = localStorage.getItem(STORAGE_DATE_FROM);
    const to = localStorage.getItem(STORAGE_DATE_TO);
    if (from && to) return [dayjs(from), dayjs(to)];
    return defaultRange();
  });

  function handleRangeChange(dates: [Dayjs | null, Dayjs | null] | null) {
    if (!dates || !dates[0] || !dates[1]) return;
    let [from, to] = dates;
    if (to.diff(from, 'day') > MAX_PERIOD_DAYS) to = from.add(MAX_PERIOD_DAYS, 'day');
    setRange([from, to]);
    localStorage.setItem(STORAGE_DATE_FROM, from.format(API_DATE_FORMAT));
    localStorage.setItem(STORAGE_DATE_TO, to.format(API_DATE_FORMAT));
  }

  return [range, handleRangeChange] as const;
}
