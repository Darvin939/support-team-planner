import {useEffect, useLayoutEffect, useRef, useState} from 'react';
import type {TableColumnsType} from 'antd';
import {Alert, Button, Card, DatePicker, Empty, Segmented, Select, Table, Typography} from 'antd';
import dayjs from 'dayjs';
import {useTeams} from '../hooks/useTeams';
import {useDateRangeFilter} from '../hooks/useDateRangeFilter';
import {useIsMobile} from '../hooks/useIsMobile';
import {API_DATE_FORMAT, DISPLAY_DATE_FORMAT} from '../lib/dateFormats';
import {StatTile} from '../components/StatTile';
import {FilterField, FilterGrid} from '../components/FilterGrid';
import {CriticalityBadge} from '../components/planningBadges';
import {NAME_COLUMN_WIDTH} from '../lib/layout';
import {DEFAULT_PAGE_SIZE} from '../lib/pagination';
import {AppPagination} from '../components/AppPagination';
import {readStoredJson, writeStoredJson} from '../lib/storage';
import {usePaginationState} from '../hooks/usePaginationState';
import {useStatisticsCalendar} from '../hooks/useStatisticsCalendar';
import {StatisticsCalendar} from '../components/StatisticsCalendar';
import {ASSIGNMENT_STATUS_LABELS, type AssignmentStatus} from '../domain/types';
import {
  type ActiveAssignment,
  type ActiveAssignmentsResponse,
  useActiveAssignments,
} from '../hooks/useStatisticsData';

const STORAGE_STATS_TEAMS = 'statsSelectedTeams';

function buildColumns(showDate: boolean): TableColumnsType<ActiveAssignment> {
  const cols: TableColumnsType<ActiveAssignment> = [
    {
      title: 'Работа',
      dataIndex: 'task_name',
      key: 'task_name',
      width: NAME_COLUMN_WIDTH,
      render: (v: string) => <span style={{overflowWrap: 'anywhere'}}>{v}</span>,
    },
    {title: 'Команда', dataIndex: 'team_name', key: 'team_name'},
    {title: 'Крит.', dataIndex: 'criticality', key: 'criticality', render: (v) => <CriticalityBadge value={v}/>},
  ];
  if (showDate) cols.push({title: 'Дата', dataIndex: 'date', key: 'date'});
  cols.push(
    {title: 'Блок', dataIndex: 'block', key: 'block'},
    {title: 'Статус', dataIndex: 'status', key: 'status', render: (v: string) =>
      ASSIGNMENT_STATUS_LABELS[v as AssignmentStatus] ?? v},
    {title: 'Исполнитель', dataIndex: 'user_name', key: 'user_name'},
    {title: 'Комментарий', dataIndex: 'comment', key: 'comment'},
  );
  return cols;
}

function StatsSection({
                        title,
                        response,
                        showDate,
                        page,
                        pageSize,
                        onChange,
                        onPageSizeChange,
                        loading,
                        error,
                        fetching,
                        onRetry,
                        showSummary,
                      }: {
  title: string;
  response: ActiveAssignmentsResponse | undefined;
  showDate: boolean;
  page: number;
  pageSize: number;
  onChange: (page: number, pageSize: number) => void;
  onPageSizeChange: (size: number) => void;
  loading: boolean;
  error: boolean;
  fetching: boolean;
  onRetry: () => void;
  showSummary: boolean;
}) {
  const [lastResult, setLastResult] = useState<{title: string; response: ActiveAssignmentsResponse} | null>(null);
  useLayoutEffect(() => {
    if (!loading && !error && response) setLastResult({title, response});
  }, [loading, error, response, title]);
  // Keep the previous result under its own date until the requested result arrives.
  // The parent remounts this section on team/mode changes to avoid mixing contexts.
  const visibleResponse = loading ? lastResult?.response : response;
  const visibleTitle = loading && lastResult ? lastResult.title : title;
  const items = visibleResponse?.items ?? [];
  const total = visibleResponse?.total ?? 0;
  const statusCounts = visibleResponse?.stats.status ?? {new: 0, planned: 0};
  const critCounts = visibleResponse?.stats.criticality ?? {high: 0, medium: 0, low: 0};
  const bodyRef = useRef<HTMLDivElement>(null);
  const [reservedHeight, setReservedHeight] = useState(240);
  useLayoutEffect(() => {
    if (!loading && !error && bodyRef.current) setReservedHeight(bodyRef.current.offsetHeight);
  }, [loading, error, response]);

  return (
    <Card style={{marginBottom: 16, minWidth: 0}}>
      <Typography.Title level={4} style={{marginTop: 0}}>
        {visibleTitle}
      </Typography.Title>
      <div className="statistics-details-status" role="status">
        {loading || fetching ? <span className="statistics-loading">{loading && lastResult ? `Загрузка: ${title.toLowerCase()}…` : 'Загрузка работ…'}</span> : null}
      </div>
      <div ref={bodyRef} style={loading ? {minHeight: reservedHeight} : undefined} aria-busy={loading || fetching}>
      {error ? <Alert type="error" showIcon title="Не удалось загрузить работы"
                      action={<Button onClick={onRetry} loading={fetching}>Повторить</Button>}/> :
        loading && !visibleResponse ? <div className="statistics-loading" role="status" aria-label="Загрузка работ">Загрузка работ…</div> : <>
      {showSummary && <div className="statistics-summary-groups">
        <div className="statistics-summary-group">
        <Typography.Text type="secondary">Активные работы</Typography.Text>
        <StatTile label="Всего" value={total} primary/>
        </div>
        <div className="statistics-summary-group">
        <Typography.Text type="secondary">Статус</Typography.Text>
        <div className="statistics-summary-tiles">
        <StatTile label="Новый" value={statusCounts.new} accent="#1668dc"/>
        <StatTile label="Запланировано" value={statusCounts.planned} accent="#d89614"/>
        </div>
        </div>
        <div className="statistics-summary-group">
        <Typography.Text type="secondary">Критичность</Typography.Text>
        <div className="statistics-summary-tiles">
        <StatTile label="Высокая" value={critCounts.high} accent="#d32029"/>
        <StatTile label="Средняя" value={critCounts.medium} accent="#d89614"/>
        <StatTile label="Низкая" value={critCounts.low} accent="#49aa19"/>
        </div>
        </div>
      </div>}
      {total > 0 ?
        <Table rowKey="id" columns={buildColumns(showDate)} dataSource={items} pagination={false} size="small"
               scroll={{x: 'max-content'}}/> :
        <Empty description="Нет активных работ"/>}
      <div style={loading ? {visibility: 'hidden'} : undefined}>
      <AppPagination current={page} pageSize={pageSize} total={visibleResponse?.total} allowPageSizeChange
                     onChange={(nextPage, size) => size !== pageSize
                       ? onPageSizeChange(size) : onChange(nextPage, size)}/>
      </div>
      </>}
      </div>
    </Card>
  );
}

export function StatisticsPage() {
  const {data: teams} = useTeams();
  const isMobile = useIsMobile();

  const [selectedTeamIds, setSelectedTeamIds] = useState<number[]>(() => readStoredJson(STORAGE_STATS_TEAMS, []));

  const [range, handleRangeChange] = useDateRangeFilter(() => [dayjs().subtract(14, 'day'), dayjs().add(14, 'day')]);
  const [mode, setMode] = useState<'day' | 'period'>('day');
  const calendar = useStatisticsCalendar(selectedTeamIds, mode === 'day');
  const detailsRef = useRef<HTMLDivElement>(null);
  const todayPagination = usePaginationState(DEFAULT_PAGE_SIZE);
  const periodPagination = usePaginationState(DEFAULT_PAGE_SIZE);
  const resetDayPage = todayPagination.reset;
  const resetPeriodPage = periodPagination.reset;
  const pageSize = todayPagination.pageSize;

  function handleTeamsChange(ids: number[]) {
    setSelectedTeamIds(ids);
    writeStoredJson(STORAGE_STATS_TEAMS, ids);
    todayPagination.reset();
    periodPagination.reset();
  }

  useEffect(() => {
    if (!teams) return;
    const allowed = new Set(teams.map((team) => team.id));
    const filtered = selectedTeamIds.filter((id) => allowed.has(id));
    if (filtered.length !== selectedTeamIds.length) {
      setSelectedTeamIds(filtered);
      writeStoredJson(STORAGE_STATS_TEAMS, filtered);
      resetDayPage();
      resetPeriodPage();
    }
  }, [teams, selectedTeamIds, resetDayPage, resetPeriodPage]);

  function handlePageSizeChange(size: number) {
    todayPagination.setPageSize(size);
    periodPagination.setPageSize(size);
  }

  const periodFrom = range[0].format(API_DATE_FORMAT);
  const periodTo = range[1].format(API_DATE_FORMAT);

  const from = mode === 'day' ? (calendar.day ?? '') : periodFrom;
  const to = mode === 'day' ? (calendar.day ?? '') : periodTo;
  const pagination = mode === 'day' ? todayPagination : periodPagination;
  const detailQuery = useActiveAssignments(from, to, selectedTeamIds, pagination.offset, pageSize, !!from);
  const dayLabel = calendar.day ? dayjs(calendar.day).locale('ru').format('D MMMM YYYY') : '';
  const selectedCount = !calendar.counts.isError && calendar.counts.data !== undefined && calendar.day
    ? (calendar.counts.data.find(item => item.date === calendar.day)?.count ?? 0) : undefined;

  function goToDetails() {
    detailsRef.current?.focus({preventScroll: true});
    detailsRef.current?.scrollIntoView({behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'start'});
  }

  return (
    <div className="statistics-page">
      <Typography.Title level={2}>Статистика</Typography.Title>

      <Card style={{marginBottom: 16}}>
        <div className="statistics-filter-toolbar">
        <FilterGrid isMobile={isMobile}>
          <FilterField label="КОМАНДА" isMobile={isMobile} mobileSpan="full">
            <Select
              aria-label="Команды"
              mode="multiple"
              allowClear
              showSearch={{optionFilterProp: 'label'}}
              placeholder="Все команды"
              style={{minWidth: isMobile ? '100%' : 300, width: isMobile ? '100%' : undefined}}
              value={selectedTeamIds}
              onChange={handleTeamsChange}
              options={teams?.map((t) => ({value: t.id, label: t.name}))}
            />
          </FilterField>
        </FilterGrid>
        <Segmented className="statistics-modes" aria-label="Режим статистики" block={isMobile}
                   value={mode} onChange={setMode}
                   options={[{label: 'По дням', value: 'day'}, {label: 'За период', value: 'period'}]}/>
        </div>
      </Card>

      {mode === 'day' ? <Card style={{marginBottom: 16}} className="statistics-calendar-card">
        <StatisticsCalendar month={calendar.month} selectedDay={calendar.day} counts={calendar.counts.data}
                            error={calendar.counts.isError} fetching={calendar.counts.isFetching}
                            onRetry={() => void calendar.counts.refetch()}
                            onNavigate={month => { todayPagination.reset(); calendar.navigate(month); }}
                            onSelect={day => { todayPagination.reset(); calendar.selectDay(day); }}/>
        <div className="statistics-day-summary">
          <div aria-live="polite">
            <Typography.Text strong>{calendar.day ? dayLabel : 'Выберите день'}</Typography.Text>
            <Typography.Text type="secondary">
              {calendar.day ? (selectedCount === undefined ? ' · количество пока недоступно' : ` · Активных работ: ${selectedCount}`) :
                (calendar.counts.isError ? ' · или повторите загрузку календаря' : ' · определяем первый день с работами…')}
            </Typography.Text>
          </div>
          <Button disabled={!calendar.day} onClick={goToDetails}>К списку работ</Button>
        </div>
      </Card> : <Card style={{marginBottom: 16}}>
        <FilterGrid isMobile={isMobile}>
          <FilterField label="ПЕРИОД" isMobile={isMobile} mobileSpan="full">
            <DatePicker.RangePicker
              classNames={{popup: {root: 'statistics-period-popup'}}}
              value={range}
              onChange={dates => { periodPagination.reset(); handleRangeChange(dates); }}
              format={DISPLAY_DATE_FORMAT}
              minDate={dayjs('2000-01-01')}
              maxDate={dayjs('2099-12-31')}
              allowClear
              style={isMobile ? {width: '100%'} : undefined}
            />
          </FilterField>
        </FilterGrid>
      </Card>}
      <Typography.Paragraph type="secondary">
        Учитываются активные назначения со статусами «Новый» и «Запланировано».
        Одна работа на нескольких датах учитывается на каждой из них.
      </Typography.Paragraph>
      <div ref={detailsRef} tabIndex={-1} className="statistics-details" aria-label="Список активных работ">
      <StatsSection
        key={`${mode}:${selectedTeamIds.join(',')}`}
        title={mode === 'day' ? (calendar.day ? `Работы на ${dayLabel}` : 'Работы выбранного дня') : `Работы за период ${range[0].format(DISPLAY_DATE_FORMAT)} — ${range[1].format(DISPLAY_DATE_FORMAT)}`}
        response={detailQuery.data}
        showDate={mode === 'period'}
        loading={detailQuery.isPending || (mode === 'day' && !calendar.day)}
        error={detailQuery.isError}
        fetching={detailQuery.isFetching}
        onRetry={() => void detailQuery.refetch()}
        page={pagination.page}
        pageSize={pageSize}
        onChange={pagination.onChange}
        onPageSizeChange={handlePageSizeChange}
        showSummary
      />
      </div>
    </div>
  );
}
