import {useEffect, useState} from 'react';
import type {TableColumnsType} from 'antd';
import {Card, DatePicker, Empty, Select, Space, Table, Typography} from 'antd';
import dayjs from 'dayjs';
import {useTeams} from '../hooks/useTeams';
import {useDateRangeFilter} from '../hooks/useDateRangeFilter';
import {useIsMobile} from '../hooks/useIsMobile';
import {API_DATE_FORMAT, DISPLAY_DATE_FORMAT} from '../lib/dateFormats';
import {StatGroupLabel, StatTile} from '../components/StatTile';
import {FilterField, FilterGrid} from '../components/FilterGrid';
import {CriticalityBadge} from '../components/planningBadges';
import {NAME_COLUMN_WIDTH} from '../lib/layout';
import {DEFAULT_PAGE_SIZE} from '../lib/pagination';
import {AppPagination} from '../components/AppPagination';
import {readStoredJson, writeStoredJson} from '../lib/storage';
import {usePaginationState} from '../hooks/usePaginationState';
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
                      }: {
  title: string;
  response: ActiveAssignmentsResponse | undefined;
  showDate: boolean;
  page: number;
  pageSize: number;
  onChange: (page: number, pageSize: number) => void;
  onPageSizeChange: (size: number) => void;
}) {
  const items = response?.items ?? [];
  const total = response?.total ?? 0;
  const statusCounts = response?.stats.status ?? {new: 0, planned: 0};
  const critCounts = response?.stats.criticality ?? {high: 0, medium: 0, low: 0};

  return (
    <Card style={{marginBottom: 16}}>
      <Typography.Title level={4} style={{marginTop: 0}}>
        {title}
      </Typography.Title>
      <Space size={8} wrap style={{marginBottom: 14}}>
        <StatTile label="Всего" value={total} primary/>
        <StatGroupLabel>Статус</StatGroupLabel>
        <StatTile label="Новый" value={statusCounts.new} accent="#1668dc"/>
        <StatTile label="Запланировано" value={statusCounts.planned} accent="#d89614"/>
        <StatGroupLabel>Критичность</StatGroupLabel>
        <StatTile label="Высокая" value={critCounts.high} accent="#d32029"/>
        <StatTile label="Средняя" value={critCounts.medium} accent="#d89614"/>
        <StatTile label="Низкая" value={critCounts.low} accent="#49aa19"/>
      </Space>
      {total > 0 ?
        <Table rowKey="id" columns={buildColumns(showDate)} dataSource={items} pagination={false} size="small"
               scroll={{x: 'max-content'}}/> :
        <Empty description="Нет активных работ"/>}
      <AppPagination current={page} pageSize={pageSize} total={response?.total} allowPageSizeChange
                     onChange={(nextPage, size) => size !== pageSize
                       ? onPageSizeChange(size) : onChange(nextPage, size)}/>
    </Card>
  );
}

export function StatisticsPage() {
  const {data: teams} = useTeams();
  const isMobile = useIsMobile();

  const [selectedTeamIds, setSelectedTeamIds] = useState<number[]>(() => readStoredJson(STORAGE_STATS_TEAMS, []));

  const [range, handleRangeChange] = useDateRangeFilter(() => [dayjs().subtract(14, 'day'), dayjs().add(14, 'day')]);
  const todayPagination = usePaginationState(DEFAULT_PAGE_SIZE);
  const periodPagination = usePaginationState(DEFAULT_PAGE_SIZE);
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
    }
  }, [teams, selectedTeamIds]);

  function handlePageSizeChange(size: number) {
    todayPagination.setPageSize(size);
    periodPagination.setPageSize(size);
  }

  const periodFrom = range[0].format(API_DATE_FORMAT);
  const periodTo = range[1].format(API_DATE_FORMAT);

  useEffect(() => {
    periodPagination.reset();
  }, [periodFrom, periodTo, periodPagination.reset]);

  const today = dayjs().format(API_DATE_FORMAT);
  const {data: todayData} = useActiveAssignments(today, today, selectedTeamIds, todayPagination.offset, pageSize);
  const {data: periodData} = useActiveAssignments(periodFrom, periodTo, selectedTeamIds, periodPagination.offset, pageSize);

  return (
    <>
      <Typography.Title level={2}>Статистика</Typography.Title>

      <Card style={{marginBottom: 16}}>
        <FilterGrid isMobile={isMobile}>
          <FilterField label="КОМАНДА" isMobile={isMobile} mobileSpan="full">
            <Select
              mode="multiple"
              allowClear
              showSearch={{optionFilterProp: 'label'}}
              placeholder="Все команды"
              style={{minWidth: isMobile ? '100%' : 280, width: isMobile ? '100%' : undefined}}
              value={selectedTeamIds}
              onChange={handleTeamsChange}
              options={teams?.map((t) => ({value: t.id, label: t.name}))}
            />
          </FilterField>
        </FilterGrid>
      </Card>

      <StatsSection
        title="Активные работы на сегодня"
        response={todayData}
        showDate={false}
        page={todayPagination.page}
        pageSize={pageSize}
        onChange={todayPagination.onChange}
        onPageSizeChange={handlePageSizeChange}
      />

      <Card style={{marginBottom: 16}}>
        <FilterGrid isMobile={isMobile}>
          <FilterField label="ПЕРИОД" isMobile={isMobile} mobileSpan="full">
            <DatePicker.RangePicker
              value={range}
              onChange={handleRangeChange}
              format={DISPLAY_DATE_FORMAT}
              minDate={dayjs('2000-01-01')}
              maxDate={dayjs('2099-12-31')}
              allowClear
              style={isMobile ? {width: '100%'} : undefined}
            />
          </FilterField>
        </FilterGrid>
      </Card>
      <StatsSection
        title="Активные работы за период"
        response={periodData}
        showDate
        page={periodPagination.page}
        pageSize={pageSize}
        onChange={periodPagination.onChange}
        onPageSizeChange={handlePageSizeChange}
      />
    </>
  );
}
