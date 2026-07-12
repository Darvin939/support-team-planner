import {useState} from 'react';
import dayjs, {type Dayjs} from 'dayjs';
import {API_DATE_FORMAT} from '../lib/dateFormats';

const STORAGE_DATE_FROM = 'filterDateFrom';
const STORAGE_DATE_TO = 'filterDateTo';
export const MAX_PERIOD_DAYS = 60;

type Range = [Dayjs, Dayjs];

interface UseDateRangeFilterOptions {
  storageKeyFrom?: string;
  storageKeyTo?: string;
  maxPeriodDays?: number;
  onChange?: () => void;
}

/**
 * Shared date-range filter state backing a DatePicker.RangePicker's value +
 * onChange, persisted to localStorage. Planning/Statistics pass a
 * `defaultRange` function (default 'filterDateFrom'/'filterDateTo' keys, so the
 * selected period stays in sync across both pages) — clearing the picker
 * resets to that default. Journal passes `null` instead, since clearing its
 * filter means "show all history", not a default period; it must supply its
 * own storage keys since there's no shared default to key off of.
 */
export function useDateRangeFilter(
  defaultRange: () => Range,
  options?: UseDateRangeFilterOptions,
): readonly [Range, (dates: [Dayjs | null, Dayjs | null] | null) => void];
export function useDateRangeFilter(
  defaultRange: null,
  options: UseDateRangeFilterOptions & { storageKeyFrom: string; storageKeyTo: string },
): readonly [Range | null, (dates: [Dayjs | null, Dayjs | null] | null) => void];
export function useDateRangeFilter(defaultRange: (() => Range) | null, options: UseDateRangeFilterOptions = {}) {
  const {
    storageKeyFrom = STORAGE_DATE_FROM,
    storageKeyTo = STORAGE_DATE_TO,
    maxPeriodDays = MAX_PERIOD_DAYS,
    onChange,
  } = options;

  const [range, setRange] = useState<Range | null>(() => {
    const from = localStorage.getItem(storageKeyFrom);
    const to = localStorage.getItem(storageKeyTo);
    if (from && to) return [dayjs(from), dayjs(to)];
    return defaultRange ? defaultRange() : null;
  });

  function handleRangeChange(dates: [Dayjs | null, Dayjs | null] | null) {
    if (!dates || !dates[0] || !dates[1]) {
      if (defaultRange) {
        const [from, to] = defaultRange();
        setRange([from, to]);
        localStorage.setItem(storageKeyFrom, from.format(API_DATE_FORMAT));
        localStorage.setItem(storageKeyTo, to.format(API_DATE_FORMAT));
      } else {
        setRange(null);
        localStorage.removeItem(storageKeyFrom);
        localStorage.removeItem(storageKeyTo);
      }
      onChange?.();
      return;
    }
    let [from, to] = dates;
    if (to.diff(from, 'day') > maxPeriodDays) to = from.add(maxPeriodDays, 'day');
    setRange([from, to]);
    localStorage.setItem(storageKeyFrom, from.format(API_DATE_FORMAT));
    localStorage.setItem(storageKeyTo, to.format(API_DATE_FORMAT));
    onChange?.();
  }

  return [range, handleRangeChange] as const;
}
