import {useState} from 'react';
import type {TableColumnsType} from 'antd';
import {Card, DatePicker, Empty, Select, Space, Table, Typography} from 'antd';
import {useQuery} from '@tanstack/react-query';
import dayjs, {type Dayjs} from 'dayjs';
import {useTeams} from '../hooks/useTeams';
import {StatGroupLabel, StatTile} from '../components/StatTile';
import {CriticalityBadge} from '../components/planningBadges';

const STORAGE_DATE_FROM = 'filterDateFrom';
const STORAGE_DATE_TO = 'filterDateTo';
const STORAGE_STATS_TEAMS = 'statsSelectedTeams';
const MAX_PERIOD_DAYS = 60;

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

const STATUS_LABEL: Record<string, string> = { new: 'Новый', planned: 'Запланировано', rollback: 'Откат', success: 'Успешно' };

function useActiveAssignments(from: string, to: string, teamIds: number[]) {
  return useQuery<ActiveAssignment[]>({
    queryKey: ['active-assignments', from, to, teamIds],
    queryFn: async () => {
      const teamParam = teamIds.length ? `&team_ids=${teamIds.join(',')}` : '';
      const r = await fetch(`/api/active-assignments/0?start_date=${from}&end_date=${to}${teamParam}`, { credentials: 'same-origin' });
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

function StatsSection({ title, data, showDate }: { title: string; data: ActiveAssignment[] | undefined; showDate: boolean }) {
  const statusCounts = { new: 0, planned: 0 };
  const critCounts = { high: 0, medium: 0, low: 0 };
  (data ?? []).forEach((a) => {
    if (a.status in statusCounts) statusCounts[a.status as keyof typeof statusCounts]++;
    if (a.criticality in critCounts) critCounts[a.criticality as keyof typeof critCounts]++;
  });

  return (
    <Card style={{ marginBottom: 16 }}>
      <Typography.Title level={4} style={{ marginTop: 0 }}>
        {title}
      </Typography.Title>
      <Space size={8} wrap style={{ marginBottom: 14 }}>
        <StatTile label="Всего" value={data?.length ?? 0} primary />
        <StatGroupLabel>Статус</StatGroupLabel>
        <StatTile label="Новый" value={statusCounts.new} accent="#1668dc" />
        <StatTile label="Запланировано" value={statusCounts.planned} accent="#d89614" />
        <StatGroupLabel>Критичность</StatGroupLabel>
        <StatTile label="Высокая" value={critCounts.high} accent="#d32029" />
        <StatTile label="Средняя" value={critCounts.medium} accent="#d89614" />
        <StatTile label="Низкая" value={critCounts.low} accent="#49aa19" />
      </Space>
      {data && data.length > 0 ? (
        <Table rowKey="id" columns={buildColumns(showDate)} dataSource={data} pagination={false} size="small" scroll={{ x: true }} />
      ) : (
        <Empty description="Нет активных работ" />
      )}
    </Card>
  );
}

export function StatisticsPage() {
  const { data: teams } = useTeams();

  const [selectedTeamIds, setSelectedTeamIds] = useState<number[]>(() => {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_STATS_TEAMS) ?? '[]');
    } catch {
      return [];
    }
  });

  const [range, setRange] = useState<[Dayjs, Dayjs]>(() => {
    const from = localStorage.getItem(STORAGE_DATE_FROM);
    const to = localStorage.getItem(STORAGE_DATE_TO);
    if (from && to) return [dayjs(from), dayjs(to)];
    return [dayjs().subtract(7, 'day'), dayjs()];
  });

  function handleTeamsChange(ids: number[]) {
    setSelectedTeamIds(ids);
    localStorage.setItem(STORAGE_STATS_TEAMS, JSON.stringify(ids));
  }

  function handleRangeChange(dates: [Dayjs | null, Dayjs | null] | null) {
    if (!dates || !dates[0] || !dates[1]) return;
    let [from, to] = dates;
    if (to.diff(from, 'day') > MAX_PERIOD_DAYS) to = from.add(MAX_PERIOD_DAYS, 'day');
    setRange([from, to]);
    localStorage.setItem(STORAGE_DATE_FROM, from.format('YYYY-MM-DD'));
    localStorage.setItem(STORAGE_DATE_TO, to.format('YYYY-MM-DD'));
  }

  const today = dayjs().format('YYYY-MM-DD');
  const { data: todayData } = useActiveAssignments(today, today, selectedTeamIds);
  const { data: periodData } = useActiveAssignments(range[0].format('YYYY-MM-DD'), range[1].format('YYYY-MM-DD'), selectedTeamIds);

  return (
    <>
      <Typography.Title level={2}>Статистика</Typography.Title>

      <Card style={{ marginBottom: 16 }}>
        <Space align="center">
          <span>Команда:</span>
          <Select
            mode="multiple"
            allowClear
            placeholder="Все команды"
            style={{ minWidth: 280 }}
            value={selectedTeamIds}
            onChange={handleTeamsChange}
            options={teams?.map((t) => ({ value: t.id, label: t.name }))}
          />
        </Space>
      </Card>

      <StatsSection title="Активные работы на сегодня" data={todayData} showDate={false} />

      <Card style={{ marginBottom: 16 }}>
        <Space>
          <span>Период:</span>
          <DatePicker.RangePicker
            value={range}
            onChange={handleRangeChange}
            minDate={dayjs('2000-01-01')}
            maxDate={dayjs('2099-12-31')}
            allowClear={false}
          />
        </Space>
      </Card>
      <StatsSection title="Активные работы за период" data={periodData} showDate />
    </>
  );
}
