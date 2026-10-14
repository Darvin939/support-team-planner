import {useEffect, useState} from 'react';
import dayjs, {type Dayjs} from 'dayjs';
import {API_DATE_FORMAT} from '../lib/dateFormats';
import {getInitialStatisticsDay} from '../lib/statisticsCalendar';
import {getStatisticsCalendarRange, useActiveAssignmentDateCounts} from './useStatisticsData';

export function useStatisticsCalendar(teamIds: number[], enabled: boolean) {
  const [selection, setSelection] = useState(() => ({
    month: dayjs().startOf('month'),
    day: dayjs().format(API_DATE_FORMAT) as string | null,
  }));
  const range = getStatisticsCalendarRange(selection.month);
  const counts = useActiveAssignmentDateCounts(range.from, range.to, teamIds, enabled);

  useEffect(() => {
    if (selection.day !== null || !counts.isSuccess) return;
    const day = getInitialStatisticsDay(selection.month, counts.data);
    setSelection(current => current === selection ? {...current, day} : current);
  }, [selection, counts.isSuccess, counts.data]);

  function navigate(month: Dayjs) {
    const today = dayjs();
    setSelection({
      month: month.startOf('month'),
      day: month.isSame(today, 'month') ? today.format(API_DATE_FORMAT) : null,
    });
  }

  function selectDay(day: string) {
    setSelection(current => ({...current, day}));
  }

  return {...selection, counts, navigate, selectDay};
}
