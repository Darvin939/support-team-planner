import {useEffect, useState} from 'react';
import {useNavigate, useParams} from 'react-router-dom';
import {Card, DatePicker, Empty, Input, Modal, Pagination, Select, Spin, Tag, Typography} from 'antd';
import {useQuery} from '@tanstack/react-query';
import dayjs, {type Dayjs} from 'dayjs';
import {useTeams} from '../hooks/useTeams';
import {useEmployeeNames, useEmployeeOptions} from '../hooks/useEmployeeNames';
import {useIsMobile} from '../hooks/useIsMobile';
import {FilterField, FilterGrid} from '../components/FilterGrid';
import {formatChangedBy, formatHistoryText, type HistoryEntry} from '../lib/historyFormat';
import {API_DATE_FORMAT, DISPLAY_DATE_FORMAT} from '../lib/dateFormats';

const JOURNAL_PAGE_SIZE = 20;
const HISTORY_PAGE_SIZE = 10;
const STORAGE_TEAM_ID = 'selectedTeamId';
const STORAGE_DATE_FROM = 'journalDateFrom';
const STORAGE_DATE_TO = 'journalDateTo';

interface JournalItem extends HistoryEntry {
  task_id: number;
}

interface JournalFilters {
  search: string;
  dateFrom: string | null;
  dateTo: string | null;
  changedByEmployeeId: number | null;
}

function useJournal(teamId: number | undefined, offset: number, filters: JournalFilters) {
  return useQuery<{ items: JournalItem[]; total: number }>({
    queryKey: ['journal', teamId, offset, filters],
    enabled: teamId !== undefined,
    queryFn: async () => {
      const params = new URLSearchParams({ offset: String(offset), limit: String(JOURNAL_PAGE_SIZE) });
      if (filters.search) params.set('search', filters.search);
      if (filters.dateFrom) params.set('date_from', filters.dateFrom);
      if (filters.dateTo) params.set('date_to', filters.dateTo);
      if (filters.changedByEmployeeId) params.set('changed_by_employee_id', String(filters.changedByEmployeeId));
      const r = await fetch(`/api/journal/${teamId}?${params}`, { credentials: 'same-origin' });
      if (!r.ok) throw new Error(`GET /api/journal -> ${r.status}`);
      return r.json();
    },
  });
}

function useTaskHistory(taskId: number | null, offset: number) {
  return useQuery<{ history: HistoryEntry[]; total: number }>({
    queryKey: ['task-history', taskId, offset],
    enabled: taskId !== null,
    queryFn: async () => {
      const r = await fetch(`/api/task/${taskId}/history?offset=${offset}&limit=${HISTORY_PAGE_SIZE}`, { credentials: 'same-origin' });
      if (!r.ok) throw new Error(`GET /api/task/history -> ${r.status}`);
      return r.json();
    },
  });
}

function TaskHistoryModal({ taskId, taskName, onClose }: { taskId: number | null; taskName: string | null; onClose: () => void }) {
  const [offset, setOffset] = useState(0);
  const { data, isLoading } = useTaskHistory(taskId, offset);
  const getEmployeeName = useEmployeeNames();

  useEffect(() => {
    if (taskId !== null) setOffset(0);
  }, [taskId]);

  return (
    <Modal title={taskName ? `История задачи: ${taskName}` : 'История задачи'} open={taskId !== null} onCancel={onClose} footer={null} width={700}>
      {isLoading && <Spin />}
      {data && data.history.length === 0 && <Empty description="Изменений пока нет" />}
      {data && data.history.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {data.history.map((entry) => (
            <div key={`${entry.entity}-${entry.id}`} style={{ fontSize: '0.85rem', padding: '6px 10px', background: 'rgba(128,128,128,0.08)', borderRadius: 4 }}>
              <div style={{ opacity: 0.6, fontSize: '0.78rem' }}>
                {entry.changed_at} — {formatChangedBy(entry)}
              </div>
              <div>{formatHistoryText(entry, getEmployeeName, false)}</div>
            </div>
          ))}
        </div>
      )}
      {data && data.total > HISTORY_PAGE_SIZE && (
        <Pagination
          style={{ marginTop: 12, textAlign: 'center' }}
          simple
          showSizeChanger={false}
          current={Math.floor(offset / HISTORY_PAGE_SIZE) + 1}
          pageSize={HISTORY_PAGE_SIZE}
          total={data.total}
          onChange={(page) => setOffset((page - 1) * HISTORY_PAGE_SIZE)}
        />
      )}
    </Modal>
  );
}

export function JournalPage() {
  const { teamId: teamIdParam } = useParams();
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const { data: teams } = useTeams();
  const employeeOptions = useEmployeeOptions();
  const [offset, setOffset] = useState(0);
  const [modalTask, setModalTask] = useState<{ id: number; name: string } | null>(null);
  const getEmployeeName = useEmployeeNames();

  const [search, setSearch] = useState('');
  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs] | null>(() => {
    const from = localStorage.getItem(STORAGE_DATE_FROM);
    const to = localStorage.getItem(STORAGE_DATE_TO);
    return from && to ? [dayjs(from), dayjs(to)] : null;
  });
  const [changedByEmployeeId, setChangedByEmployeeId] = useState<number | null>(null);

  const teamId = teamIdParam ? Number(teamIdParam) : undefined;

  useEffect(() => {
    if (teamId !== undefined) return;
    const saved = localStorage.getItem(STORAGE_TEAM_ID);
    if (saved && saved !== '0') navigate(`/journal/${saved}`, { replace: true });
  }, [teamId, navigate]);

  useEffect(() => {
    setOffset(0);
  }, [teamId]);

  function handleSearchChange(value: string) {
    setSearch(value);
    setOffset(0);
  }

  function handleDateRangeChange(dates: [Dayjs | null, Dayjs | null] | null) {
    if (!dates || !dates[0] || !dates[1]) {
      setDateRange(null);
      localStorage.removeItem(STORAGE_DATE_FROM);
      localStorage.removeItem(STORAGE_DATE_TO);
      setOffset(0);
      return;
    }
    const [from, to] = dates;
    setDateRange([from, to]);
    localStorage.setItem(STORAGE_DATE_FROM, from.format(API_DATE_FORMAT));
    localStorage.setItem(STORAGE_DATE_TO, to.format(API_DATE_FORMAT));
    setOffset(0);
  }

  function handleChangedByChange(value: number | undefined) {
    setChangedByEmployeeId(value ?? null);
    setOffset(0);
  }

  const filters: JournalFilters = {
    search,
    dateFrom: dateRange ? dateRange[0].format(API_DATE_FORMAT) : null,
    dateTo: dateRange ? dateRange[1].format(API_DATE_FORMAT) : null,
    changedByEmployeeId,
  };

  const { data } = useJournal(teamId, offset, filters);

  function handleTeamSelect(value: number | undefined) {
    localStorage.setItem(STORAGE_TEAM_ID, value ? String(value) : '');
    navigate(value ? `/journal/${value}` : '/journal');
  }

  return (
    <>
      <Typography.Title level={2}>Журнал изменений</Typography.Title>

      <Card style={{ marginBottom: 16 }}>
        <Select
          style={{ minWidth: 260 }}
          placeholder="-- Выберите команду --"
          value={teamId}
          onChange={handleTeamSelect}
          allowClear
          showSearch={{ optionFilterProp: 'label' }}
          options={teams?.map((t) => ({ value: t.id, label: t.name }))}
        />
      </Card>

      {teamId === undefined ? (
        <Empty description="Выберите команду, чтобы посмотреть журнал изменений" />
      ) : (
        <>
          <Card style={{ marginBottom: 16 }}>
            <Typography.Title level={5} style={{ marginTop: 0 }}>
              Фильтры
            </Typography.Title>
            <FilterGrid isMobile={isMobile}>
              <FilterField label="ПОИСК ПО РАБОТЕ" isMobile={isMobile}>
                <Input.Search
                  style={{ width: isMobile ? '100%' : 220 }}
                  placeholder="Введите текст..."
                  allowClear
                  value={search}
                  onChange={(e) => handleSearchChange(e.target.value)}
                />
              </FilterField>
              <FilterField label="ПЕРИОД" isMobile={isMobile} mobileSpan={2}>
                <DatePicker.RangePicker
                  value={dateRange}
                  onChange={handleDateRangeChange}
                  format={DISPLAY_DATE_FORMAT}
                  minDate={dayjs('2000-01-01')}
                  maxDate={dayjs('2099-12-31')}
                  allowClear
                  style={isMobile ? { width: '100%' } : undefined}
                />
              </FilterField>
              <FilterField label="АВТОР ИЗМЕНЕНИЯ" isMobile={isMobile}>
                <Select
                  style={{ width: isMobile ? '100%' : 220 }}
                  placeholder="Все"
                  allowClear
                  showSearch={{optionFilterProp: "label"}}
                  value={changedByEmployeeId ?? undefined}
                  onChange={handleChangedByChange}
                  options={employeeOptions}
                />
              </FilterField>
            </FilterGrid>
          </Card>

          {data && data.items.length === 0 && <Empty description="Изменений пока нет" />}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16 }}>
            {data?.items.map((item) => (
              <Card
                key={`${item.entity}-${item.id}`}
                size="small"
                hoverable
                onClick={() => setModalTask({ id: item.task_id, name: item.task_name ?? '' })}
                styles={{ body: { fontSize: '0.9rem' } }}
              >
                <div style={{ opacity: 0.6, fontSize: '0.8rem' }}>
                  {item.changed_at} — {formatChangedBy(item)}
                </div>
                <div>
                  «{item.task_name}»{item.task_is_deleted ? <Tag style={{ marginLeft: 6 }}>удалена</Tag> : null} —{' '}
                  {formatHistoryText(item, getEmployeeName, true)}
                </div>
              </Card>
            ))}
          </div>
          {data && data.total > JOURNAL_PAGE_SIZE && (
            <Pagination
              style={{ textAlign: 'center' }}
              current={Math.floor(offset / JOURNAL_PAGE_SIZE) + 1}
              pageSize={JOURNAL_PAGE_SIZE}
              total={data.total}
              onChange={(page) => setOffset((page - 1) * JOURNAL_PAGE_SIZE)}
              showSizeChanger={false}
            />
          )}
        </>
      )}

      <TaskHistoryModal taskId={modalTask?.id ?? null} taskName={modalTask?.name ?? null} onClose={() => setModalTask(null)} />
    </>
  );
}
