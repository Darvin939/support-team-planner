import dayjs from 'dayjs';
import {API_DATE_FORMAT} from './dateFormats';

export interface TemplateBlock {
  id: number;
  name: string;
  shift_days: number;
}

/** Пятница и суббота исключаются из автоназначения наравне с днями фриза. */
function isExcludedAutoAssignDay(d: dayjs.Dayjs, freezeDays: Set<string>): boolean {
  const dow = d.day();
  return dow === 5 || dow === 6 || freezeDays.has(d.format(API_DATE_FORMAT));
}

/** Даты блоков шаблона от базовой даты — с обходом дней фриза, пятниц и суббот день за днём
 * (сдвиг накапливается, чтобы несколько блоков подряд на исключённых днях не съехали на одну дату). */
export function computeAutoAssignDates(baseDateStr: string, blocks: TemplateBlock[], freezeDays: Set<string>): Record<number, string> {
  const sorted = [...blocks].sort((a, b) => a.shift_days - b.shift_days);
  let offset = 0;
  const result: Record<number, string> = {};
  sorted.forEach((block) => {
    let d = dayjs(baseDateStr).add(block.shift_days + offset, 'day');
    while (isExcludedAutoAssignDay(d, freezeDays)) {
      d = d.add(1, 'day');
      offset += 1;
    }
    result[block.id] = d.format(API_DATE_FORMAT);
  });
  return result;
}

/** Диапазон дат для мини-таблицы автоназначения: от базовой даты до самой поздней
 * вычисленной даты блока + 5 дней запаса (чтобы можно было вручную подвинуть блок дальше). */
export function getAutoScheduleDateRange(baseDateStr: string, autoAssignDates: Record<number, string>): string[] {
  let maxDate = dayjs(baseDateStr);
  Object.values(autoAssignDates).forEach((dateStr) => {
    const d = dayjs(dateStr);
    if (d.isAfter(maxDate)) maxDate = d;
  });
  maxDate = maxDate.add(5, 'day');

  const dates: string[] = [];
  let cur = dayjs(baseDateStr);
  while (!cur.isAfter(maxDate)) {
    dates.push(cur.format(API_DATE_FORMAT));
    cur = cur.add(1, 'day');
  }
  return dates;
}
