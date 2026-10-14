import {type CSSProperties, useMemo} from 'react';
import {LeftOutlined, RightOutlined} from '@ant-design/icons';
import {Alert, Button, Space, Typography, theme} from 'antd';
import dayjs, {type Dayjs} from 'dayjs';
import 'dayjs/locale/ru';
import {API_DATE_FORMAT} from '../lib/dateFormats';
import {getMonthDays} from '../lib/statisticsCalendar';
import type {ActiveAssignmentDateCount} from '../hooks/useStatisticsData';

interface Props {
  month: Dayjs;
  selectedDay: string | null;
  counts: ActiveAssignmentDateCount[] | undefined;
  error: boolean;
  fetching: boolean;
  onRetry: () => void;
  onNavigate: (month: Dayjs) => void;
  onSelect: (day: string) => void;
}

export function StatisticsCalendar({month, selectedDay, counts, error, fetching, onRetry, onNavigate, onSelect}: Props) {
  const {token} = theme.useToken();
  const byDate = useMemo(() => new Map(counts?.map(item => [item.date, item.count])), [counts]);
  const known = counts !== undefined && !error;
  const today = dayjs().format(API_DATE_FORMAT);
  const colors = {
    '--calendar-border': token.colorBorderSecondary,
    '--calendar-primary': token.colorPrimary,
    '--calendar-selected': token.colorPrimaryBg,
    '--calendar-hover': token.colorFillSecondary,
    '--calendar-text': token.colorText,
    '--calendar-muted': token.colorTextSecondary,
    '--calendar-bg': token.colorBgContainer,
    '--calendar-weekend': token.colorWarning,
  } as CSSProperties;

  return (
    <section className="statistics-calendar" style={colors} aria-label="Календарь активных работ">
      <div className="statistics-calendar-toolbar">
        <div>
          <Typography.Title level={4} style={{margin: 0}}>Активные работы по дням</Typography.Title>
        </div>
        <Space wrap>
          <Button aria-label="Предыдущий месяц" icon={<LeftOutlined/>}
                  disabled={month.format('YYYY-MM') <= '2000-01'} onClick={() => onNavigate(month.subtract(1, 'month'))}/>
          <span className="statistics-calendar-month" aria-live="polite">{month.locale('ru').format('MMMM YYYY')}</span>
          <Button aria-label="Следующий месяц" icon={<RightOutlined/>}
                  disabled={month.format('YYYY-MM') >= '2099-12'} onClick={() => onNavigate(month.add(1, 'month'))}/>
          <Button onClick={() => onNavigate(dayjs())}>Сегодня</Button>
        </Space>
      </div>
      {error && <Alert type="error" showIcon title="Не удалось загрузить количество работ по датам"
                       action={<Button size="small" onClick={onRetry} loading={fetching}>Повторить</Button>}/>}
      <div className="statistics-calendar-status" role="status">
        {fetching ? <span className="statistics-loading">{known ? 'Обновление количества работ…' : 'Загрузка количества работ…'}</span> : 'Число работ · выберите день для просмотра'}
      </div>
      <div className="statistics-calendar-grid">
        {['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map(label =>
          <span className="statistics-calendar-weekday" key={label}>{label}</span>)}
        {getMonthDays(month).map((date, index) => {
          if (!date) return <span key={`empty-${index}`} aria-hidden="true"/>;
          const key = date.format(API_DATE_FORMAT);
          const count = known ? (byDate.get(key) ?? 0) : undefined;
          const isToday = key === today;
          const isWeekend = date.day() === 0 || date.day() === 6;
          return (
            <button type="button" key={key} data-date={key}
                    className="statistics-calendar-day" data-today={isToday || undefined}
                    data-weekend={isWeekend || undefined}
                    aria-current={isToday ? 'date' : undefined} aria-pressed={key === selectedDay}
                    aria-label={`${date.locale('ru').format('D MMMM YYYY')}${isToday ? ', сегодня' : ''}: ${count === undefined ? (error ? 'количество недоступно' : 'загрузка количества') : `активных работ — ${count}`}`}
                    onClick={() => onSelect(key)}>
              <span className="statistics-calendar-date">{date.date()}{isToday && <span className="statistics-calendar-today-mark" aria-hidden="true"> •</span>}</span>
              <span className="statistics-calendar-count" data-empty={count === 0 || undefined} aria-hidden="true">{count ?? '—'}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
