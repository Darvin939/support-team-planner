import dayjs, {type Dayjs} from 'dayjs';

export type PlanningDateRangePreset = {
  label: string;
  value: [Dayjs, Dayjs];
};

function mondayStart(date: Dayjs): Dayjs {
  const daysSinceMonday = (date.day() + 6) % 7;
  return date.startOf('day').subtract(daysSinceMonday, 'day');
}

export function getPlanningDateRangePresets(todayInput: Dayjs = dayjs()): PlanningDateRangePreset[] {
  const today = todayInput.startOf('day');
  const weekStart = mondayStart(today);

  return [
    {label: 'Прошлые 30 дней', value: [today.subtract(29, 'day'), today]},
    {label: 'Прошлые 7', value: [today.subtract(6, 'day'), today]},
    {label: 'Эта неделя', value: [weekStart, weekStart.add(6, 'day')]},
    {label: '±7 дней', value: [today.subtract(6, 'day'), today.add(7, 'day')]},
    {label: '±14 дней', value: [today.subtract(13, 'day'), today.add(14, 'day')]},
  ];
}
