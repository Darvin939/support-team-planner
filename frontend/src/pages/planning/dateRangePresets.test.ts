import dayjs from 'dayjs';
import {describe, expect, it} from 'vitest';
import {getPlanningDateRangePresets} from './dateRangePresets';

describe('getPlanningDateRangePresets', () => {
  it('returns the agreed ranges with exact inclusive lengths', () => {
    const presets = getPlanningDateRangePresets(dayjs('2026-09-16'));

    expect(presets.map(({label}) => label)).toEqual(['Прошлые 30 дней', 'Прошлые 7', 'Эта неделя', '±7 дней', '±14 дней']);
    expect(presets.map(({value: [from, to]}) => [from.format('YYYY-MM-DD'), to.format('YYYY-MM-DD')])).toEqual([
      ['2026-08-18', '2026-09-16'],
      ['2026-09-10', '2026-09-16'],
      ['2026-09-14', '2026-09-20'],
      ['2026-09-10', '2026-09-23'],
      ['2026-09-03', '2026-09-30'],
    ]);
    expect(presets.map(({value: [from, to]}) => to.diff(from, 'day') + 1)).toEqual([30, 7, 7, 14, 28]);
  });

  it('calculates Monday independently of the locale and crosses month boundaries', () => {
    const presets = getPlanningDateRangePresets(dayjs('2026-01-01'));

    expect(presets[2].value.map((date) => date.format('YYYY-MM-DD'))).toEqual(['2025-12-29', '2026-01-04']);
    expect(presets[3].value.map((date) => date.format('YYYY-MM-DD'))).toEqual(['2025-12-26', '2026-01-08']);
  });
});
