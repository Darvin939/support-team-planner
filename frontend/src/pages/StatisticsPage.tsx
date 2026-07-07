import {useEffect, useState} from 'react';
import type {TableColumnsType} from 'antd';
import {Card, DatePicker, Empty, Pagination, Select, Space, Table, Typography} from 'antd';
import {useQuery} from '@tanstack/react-query';
import dayjs from 'dayjs';
import {useTeams} from '../hooks/useTeams';
import {useDateRangeFilter} from '../hooks/useDateRangeFilter';
import {useIsMobile} from '../hooks/useIsMobile';
import {API_DATE_FORMAT, DISPLAY_DATE_FORMAT} from '../lib/dateFormats';
import {StatGroupLabel, StatTile} from '../components/StatTile';
import {FilterField, FilterGrid} from '../components/FilterGrid';
import {CriticalityBadge} from '../components/planningBadges';

const STORAGE_STATS_TEAMS = 'statsSelectedTeams';
const STATS_PAGE_SIZE = 20;

interface ActiveAssignment {
  id: number;
  task_name: string;
  team_name: string | null;
  criticality: 'high' | 'medium' | 'low';
  date: string;
  block: string | null;
  status: 'new' | 'planned' | 'rollback' | 'success';
  employee_name: string | null;
  comment: string | null;
}

interface ActiveAssignmentsResponse {
  items: ActiveAssignment[];
  total: number;
  stats: {
    status: { new: number; planned: number };
    criticality: { high: number; medium: number; low: number };
  };
}

const STATUS_LABEL: Record<string, string> = { new: 'Новый', planned: 'Запланировано', rollback: 'Откат', success: 'Успешно' };

function useActiveAssignments(from: string, to: string, teamIds: number[], offset: number) {
  return useQuery<ActiveAssignmentsResponse>({
    queryKey: ['active-assignments', from, to, teamIds, offset],
    queryFn: async () => {
      const teamParam = teamIds.length ? `&team_ids=${teamIds.join(',')}` : '';
      const r = await fetch(
        `/api/active-assignments/0?start_date=${from}&end_date=${to}${teamParam}&offset=${offset}&limit=${STATS_PAGE_SIZE}`,
        { credentials: 'same-origin' }
      );
      if (!r.ok) throw new Error(`GET /api/active-assignments -> ${r.status}`);
      return r.json();
    },
  });
}

function buildColumns(showDate: boolean): TableColumnsType<ActiveAssignment> {
  const cols: TableColumnsType<ActiveAssignment> = [
    { title: 'Работа', dataIndex: 'task_name', key: 'task_name' },
    { title: 'Команда', dataIndex: 'team_name', key: 'team_name' },
    { title: 'Крит.', dataIndex: 'criticality', key: 'criticality', render: (v) => <CriticalityBadge value={v} /> },
  ];
  if (showDate) cols.push({ title: 'Дата', dataIndex: 'date', key: 'date' });
  cols.push(
    { title: 'Блок', dataIndex: 'block', key: 'block' },
    { title: 'Статус', dataIndex: 'status', key: 'status', render: (v) => STATUS_LABEL[v] ?? v },
    { title: 'Исполнитель', dataIndex: 'employee_name', key: 'employee_name' },
    { title: 'Комментарий', dataIndex: 'comment', key: 'comment' },
  );
  return cols;
}

function StatsSection({
  title,
  response,
  showDate,
  offset,
  onPageChange,
}: {
  title: string;
  response: ActiveAssignmentsResponse | undefined;
  showDate: boolean;
  offset: number;
  onPageChange: (offset: number) => void;
}) {
  const items = response?.items ?? [];
  const total = response?.total ?? 0;
  const statusCounts = response?.stats.status ?? { new: 0, planned: 0 };
  const critCounts = response?.stats.criticality ?? { high: 0, medium: 0, low: 0 };

  return (
    <Card style={{ marginBottom: 16 }}>
      <Typography.Title level={4} style={{ marginTop: 0 }}>
        {title}
      </Typography.Title>
      <Space size={8} wrap style={{ marginBottom: 14 }}>
        <StatTile label="Всего" value={total} primary />
        <StatGroupLabel>Статус</StatGroupLabel>
        <StatTile label="Новый" value={statusCounts.new} accent="#1668dc" />
        <StatTile label="Запланировано" value={statusCounts.planned} accent="#d89614" />
        <StatGroupLabel>Критичность</StatGroupLabel>
        <StatTile label="Высокая" value={critCounts.high} accent="#d32029" />
        <StatTile label="Средняя" value={critCounts.medium} accent="#d89614" />
        <StatTile label="Низкая" value={critCounts.low} accent="#49aa19" />
      </Space>
      {total > 0 ? (
        <>
          <Table rowKey="id" columns={buildColumns(showDate)} dataSource={items} pagination={false} size="small" scroll={{ x: true }} />
          {total > STATS_PAGE_SIZE && (
            <div style={{ textAlign: 'center', marginTop: 16 }}>
              <Pagination
                current={offset / STATS_PAGE_SIZE + 1}
                pageSize={STATS_PAGE_SIZE}
                total={total}
                onChange={(page) => onPageChange((page - 1) * STATS_PAGE_SIZE)}
                showSizeChanger={false}
              />
            </div>
          )}
        </>
      ) : (
        <Empty description="Нет активных работ" />
      )}
    </Card>
  );
}

export function StatisticsPage() {
  const { data: teams } = useTeams();
  const isMobile = useIsMobile();

  const [selectedTeamIds, setSelectedTeamIds] = useState<number[]>(() => {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_STATS_TEAMS) ?? '[]');
    } catch {
      return [];
    }
  });

  const [range, handleRangeChange] = useDateRangeFilter(() => [dayjs().subtract(7, 'day'), dayjs()]);
  const [todayOffset, setTodayOffset] = useState(0);
  const [periodOffset, setPeriodOffset] = useState(0);

  function handleTeamsChange(ids: number[]) {
    setSelectedTeamIds(ids);
    localStorage.setItem(STORAGE_STATS_TEAMS, JSON.stringify(ids));
    setTodayOffset(0);
    setPeriodOffset(0);
  }

  const periodFrom = range[0].format(API_DATE_FORMAT);
  const periodTo = range[1].format(API_DATE_FORMAT);

  useEffect(() => {
    setPeriodOffset(0);
  }, [periodFrom, periodTo]);

  const today = dayjs().format(API_DATE_FORMAT);
  const { data: todayData } = useActiveAssignments(today, today, selectedTeamIds, todayOffset);
  const { data: periodData } = useActiveAssignments(periodFrom, periodTo, selectedTeamIds, periodOffset);

  return (
    <>
      <Typography.Title level={2}>Статистика</Typography.Title>

      <Card style={{ marginBottom: 16 }}>
        <FilterGrid isMobile={isMobile}>
          <FilterField label="КОМАНДА" isMobile={isMobile} mobileSpan="full">
            <Select
              mode="multiple"
              allowClear
              showSearch={{ optionFilterProp: 'label' }}
              placeholder="Все команды"
              style={{ minWidth: isMobile ? '100%' : 280, width: isMobile ? '100%' : undefined }}
              value={selectedTeamIds}
              onChange={handleTeamsChange}
              options={teams?.map((t) => ({ value: t.id, label: t.name }))}
            />
          </FilterField>
        </FilterGrid>
      </Card>

      <StatsSection
        title="Активные работы на сегодня"
        response={todayData}
        showDate={false}
        offset={todayOffset}
        onPageChange={setTodayOffset}
      />

      <Card style={{ marginBottom: 16 }}>
        <FilterGrid isMobile={isMobile}>
          <FilterField label="ПЕРИОД" isMobile={isMobile} mobileSpan="full">
            <DatePicker.RangePicker
              value={range}
              onChange={handleRangeChange}
              format={DISPLAY_DATE_FORMAT}
              minDate={dayjs('2000-01-01')}
              maxDate={dayjs('2099-12-31')}
              allowClear={false}
              style={isMobile ? { width: '100%' } : undefined}
            />
          </FilterField>
        </FilterGrid>
      </Card>
      <StatsSection
        title="Активные работы за период"
        response={periodData}
        showDate
        offset={periodOffset}
        onPageChange={setPeriodOffset}
      />
    </>
  );
}
