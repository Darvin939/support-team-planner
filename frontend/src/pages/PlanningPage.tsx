import {useEffect, useMemo, useRef, useState} from 'react';
import {useLocation, useNavigate, useParams} from 'react-router-dom';
import {DeleteOutlined, EditOutlined, InfoCircleOutlined} from '@ant-design/icons';
import type {TableColumnsType} from 'antd';
import {
  Button,
  Card,
  Checkbox,
  DatePicker,
  Empty,
  Input,
  message,
  Pagination,
  Popconfirm,
  Select,
  Space,
  Table,
  theme,
  Typography
} from 'antd';
import {useMutation, useQueryClient} from '@tanstack/react-query';
import dayjs, {type Dayjs} from 'dayjs';
import {useTeams} from '../hooks/useTeams';
import {
  type Assignment,
  type Task,
  useAssignments,
  useTaskById,
  useTaskDeps,
  useTasks,
  useTodayActive
} from '../hooks/usePlanningData';
import {useFreezeDays} from '../hooks/useSettingsData';
import {useDateRangeFilter} from '../hooks/useDateRangeFilter';
import {useIsMobile} from '../hooks/useIsMobile';
import {StatGroupLabel, StatTile} from '../components/StatTile';
import {FilterField, FilterGrid} from '../components/FilterGrid';
import {CriticalityBadge, DepBadge, ScheduleChip, TaskStatusBadge} from '../components/planningBadges';
import {TaskModal} from './planning/TaskModal';
import {AssignmentModal} from './planning/AssignmentModal';
import {useAssignmentDrag} from './planning/useAssignmentDrag';
import {useTableDragScroll} from './planning/useTableDragScroll';
import {getCellTint, getHeaderTint} from './planning/cellTint';
import {apiMutate} from '../lib/apiMutate';
import {linkify} from '../lib/linkify';
import {API_DATE_FORMAT, DISPLAY_DATE_FORMAT, DISPLAY_DATE_SHORT_FORMAT} from '../lib/dateFormats';
import {TASK_STATUS_LABELS} from '../lib/historyFormat';

const VALID_TASK_TRANSITIONS: Record<string, string[]> = {
  new: ['ready', 'in_progress', 'cancelled'],
  ready: ['in_progress', 'cancelled'],
  in_progress: ['done', 'cancelled'],
};

const STORAGE_TEAM_ID = 'selectedTeamId';
const PAGE_SIZE = 10;
// Must match TOP_BAR_HEIGHT in components/AppShell.tsx (mobile fixed top bar height).
const TOP_BAR_HEIGHT = 56;

const ASSIGNMENT_STATUS_OPTIONS = [
  { value: 'new', label: 'Новый' },
  { value: 'planned', label: 'Запланировано' },
  { value: 'rollback', label: 'Откат' },
  { value: 'success', label: 'Успешно' },
];
const CRITICALITY_OPTIONS = [
  { value: 'low', label: 'Низкая' },
  { value: 'medium', label: 'Средняя' },
  { value: 'high', label: 'Высокая' },
];
const TASK_STATUS_OPTIONS = [
  { value: 'new', label: 'Новый' },
  { value: 'ready', label: 'К планированию' },
  { value: 'in_progress', label: 'В работе' },
  { value: 'done', label: 'Выполнено' },
  { value: 'cancelled', label: 'Отменено' },
];

function dateRange(from: Dayjs, to: Dayjs): Dayjs[] {
  const dates: Dayjs[] = [];
  let cur = from;
  while (!cur.isAfter(to)) {
    dates.push(cur);
    cur = cur.add(1, 'day');
  }
  return dates;
}

function scrollGridToToday(today: string): boolean {
  const grid = document.querySelector<HTMLElement>('[data-planning-grid] .ant-table-body');
  const todayCell = document.querySelector<HTMLElement>(`[data-planning-grid] td[data-date="${today}"]`);
  const infoCell = grid?.querySelector<HTMLElement>('td:first-child') ?? null;
  if (!grid || !todayCell || !infoCell) return false;
  grid.scrollLeft = todayCell.offsetLeft - grid.offsetWidth / 2 + todayCell.offsetWidth / 2 - infoCell.offsetWidth / 2;
  return true;
}

export function PlanningPage() {
  const { teamId: teamIdParam } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const jump = location.state as { jumpTaskId?: number; jumpDate?: string } | null;
  const { data: teams } = useTeams();
  const { token } = theme.useToken();
  const teamId = teamIdParam ? Number(teamIdParam) : undefined;
  const isMobile = useIsMobile();

  const [range, handleRangeChange] = useDateRangeFilter(() => [dayjs().subtract(7, 'day'), dayjs().add(30, 'day')]);
  const [search, setSearch] = useState('');
  const [showCompleted, setShowCompleted] = useState(false);
  const [page, setPage] = useState(1);
  const [critFilter, setCritFilter] = useState<string[]>([]);
  const [statusFilter, setStatusFilter] = useState<string[]>([]);
  const [taskStatusFilter, setTaskStatusFilter] = useState<string[]>([]);
  const [taskModal, setTaskModal] = useState<{ open: boolean; task: Task | null }>({ open: false, task: null });
  const [assignmentModal, setAssignmentModal] = useState<{ open: boolean; task: Task | null; date: string | null; assignment: Assignment | null }>({
    open: false,
    task: null,
    date: null,
    assignment: null,
  });
  const queryClient = useQueryClient();
  const { data: freezeDaysList } = useFreezeDays();
  const freezeDays = useMemo(() => new Set(freezeDaysList ?? []), [freezeDaysList]);

  const statusMutation = useMutation({
    mutationFn: ({ taskId, status }: { taskId: number; status: string }) => apiMutate(`/api/tasks/${taskId}/status`, 'PATCH', { status }).then(() => ({ taskId, status })),
    onSuccess: ({ taskId, status }) => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      queryClient.invalidateQueries({ queryKey: ['active-assignments'] });
      pendingCenterRef.current = true;
      const task = taskData?.tasks.find((t) => t.id === taskId);
      if (status === 'done' || status === 'cancelled') {
        message.success(`«${task?.name ?? taskId}» — ${TASK_STATUS_LABELS[status] ?? status}`);
      }
    },
    onError: (e: Error) => message.error(e.message),
  });

  const deleteTaskMutation = useMutation({
    mutationFn: (taskId: number) => apiMutate(`/api/task/${taskId}`, 'DELETE'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      queryClient.invalidateQueries({ queryKey: ['active-assignments'] });
      pendingCenterRef.current = true;
      message.success('Задача удалена');
    },
    onError: (e: Error) => message.error(e.message),
  });

  useEffect(() => {
    if (teamId !== undefined) return;
    const saved = localStorage.getItem(STORAGE_TEAM_ID);
    if (saved && saved !== '0') navigate(`/planning/${saved}`, { replace: true });
  }, [teamId, navigate]);

  useEffect(() => setPage(1), [teamId, search, showCompleted]);

  const dateFrom = range[0].format(API_DATE_FORMAT);
  const dateTo = range[1].format(API_DATE_FORMAT);
  const today = dayjs().format(API_DATE_FORMAT);

  const { data: taskData } = useTasks(teamId ?? 0, (page - 1) * PAGE_SIZE, PAGE_SIZE, search, showCompleted);
  const taskIds = useMemo(() => taskData?.tasks.map((t) => t.id) ?? [], [taskData]);
  const { data: assignments } = useAssignments(teamId ?? 0, dateFrom, dateTo, taskIds);
  const { data: deps } = useTaskDeps(teamId ?? 0, taskIds);
  const { data: todayActive } = useTodayActive(teamId ?? 0, today);

  const assignmentByKey = useMemo(() => {
    const map = new Map<string, Assignment>();
    (assignments ?? []).forEach((a) => map.set(`${a.task_id}-${a.date}`, a));
    return map;
  }, [assignments]);

  const pendingCenterRef = useRef(true);
  const triggerCenterOnNextLoad = () => {
    pendingCenterRef.current = true;
  };

  useEffect(() => {
    if (!pendingCenterRef.current) return;
    if (scrollGridToToday(today)) pendingCenterRef.current = false;
  }, [taskData, assignments, today]);

  const { data: jumpTask } = useTaskById(teamId ?? 0, jump?.jumpTaskId ?? null);
  const { data: jumpAssignments } = useAssignments(
    teamId ?? 0,
    jump?.jumpDate ? dayjs(jump.jumpDate).subtract(60, 'day').format(API_DATE_FORMAT) : '',
    jump?.jumpDate ? dayjs(jump.jumpDate).add(60, 'day').format(API_DATE_FORMAT) : '',
    jump?.jumpTaskId ? [jump.jumpTaskId] : []
  );

  useEffect(() => {
    if (!jump?.jumpTaskId || !jump.jumpDate || !jumpTask) return;
    const assignment = (jumpAssignments ?? []).find((a) => a.date === jump.jumpDate) ?? null;
    setAssignmentModal({ open: true, task: jumpTask, date: jump.jumpDate, assignment });
    navigate(location.pathname, { replace: true, state: null });
  }, [jump, jumpTask, jumpAssignments, navigate, location.pathname]);

  const depsByTask = useMemo(() => {
    const map = new Map<number, typeof deps>();
    (deps ?? []).forEach((d) => {
      if (!map.has(d.task_id)) map.set(d.task_id, []);
      map.get(d.task_id)!.push(d);
    });
    return map;
  }, [deps]);

  const assignmentsByTask = useMemo(() => {
    const map = new Map<number, Assignment[]>();
    (assignments ?? []).forEach((a) => {
      if (!map.has(a.task_id)) map.set(a.task_id, []);
      map.get(a.task_id)!.push(a);
    });
    return map;
  }, [assignments]);

  const rescheduleMutation = useMutation({
    mutationFn: ({ assignmentId, newDate }: { assignmentId: number; newDate: string }) => {
      const existing = (assignments ?? []).find((a) => a.id === assignmentId);
      if (!existing) throw new Error('Назначение не найдено');
      return apiMutate('/api/assignment', 'POST', {
        assignment_id: existing.id,
        task_id: existing.task_id,
        date: newDate,
        block: existing.block,
        status: existing.status,
        employee_id: existing.employee_id,
        comment: existing.comment,
        is_psi: existing.is_psi,
        time_spent: existing.time_spent,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assignments'] });
      queryClient.invalidateQueries({ queryKey: ['active-assignments'] });
      message.success('Назначение перенесено');
    },
    onError: (e: Error) => message.error(e.message),
  });

  const isTaskLocked = (taskId: number) => {
    const t = taskData?.tasks.find((x) => x.id === taskId);
    return !t || t.task_status === 'done' || t.task_status === 'cancelled';
  };

  const chipDragSuppressRef = useAssignmentDrag({
    isTaskLocked,
    isOccupied: (taskId, date) => assignmentByKey.has(`${taskId}-${date}`),
    onDrop: (assignmentId, _taskId, newDate) => rescheduleMutation.mutate({ assignmentId, newDate }),
    colors: { success: token.colorSuccess, error: token.colorError },
  });

  const panSuppressRef = useTableDragScroll({ isTaskLocked });

  const filteredTasks = useMemo(() => {
    return (taskData?.tasks ?? []).filter((t) => {
      if (critFilter.length && !critFilter.includes(t.criticality)) return false;
      if (taskStatusFilter.length && !taskStatusFilter.includes(t.task_status)) return false;
      if (statusFilter.length) {
        const taskAssignments = assignmentsByTask.get(t.id) ?? [];
        if (!taskAssignments.some((a) => statusFilter.includes(a.status))) return false;
      }
      return true;
    });
  }, [taskData, critFilter, taskStatusFilter, statusFilter, assignmentsByTask]);

  function handleTeamSelect(value: number) {
    localStorage.setItem(STORAGE_TEAM_ID, String(value));
    pendingCenterRef.current = true;
    navigate(`/planning/${value}`);
  }

  const dates = useMemo(() => dateRange(range[0], range[1]), [range]);

  const columns: TableColumnsType<Task> = useMemo(() => {
    const infoColumn: TableColumnsType<Task>[number] = {
      title: 'Работа',
      dataIndex: 'name',
      key: 'name',
      fixed: 'left',
      width: 300,
      render: (_, task) => {
        const taskDeps = depsByTask.get(task.id) ?? [];
        const deleted = taskDeps.filter((d) => d.dep_is_deleted);
        const cancelled = taskDeps.filter((d) => !d.dep_is_deleted && d.dep_status === 'cancelled');
        const pending = taskDeps.filter((d) => !d.dep_is_deleted && d.dep_status !== 'done' && d.dep_status !== 'cancelled');
        const isTerminal = task.task_status === 'done' || task.task_status === 'cancelled';
        const transitions = VALID_TASK_TRANSITIONS[task.task_status] ?? [];
        return (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Button
                type="text"
                size="small"
                onClick={() => setTaskModal({ open: true, task })}
                title={isTerminal ? 'Просмотр' : 'Редактировать'}
              >
                {isTerminal ? <InfoCircleOutlined /> : <EditOutlined />}
              </Button>
              <CriticalityBadge value={task.criticality} />
              <span style={{ fontWeight: 500 }}>{task.name}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginTop: 4, flexWrap: 'wrap' }}>
              {!isTerminal && (
                <Popconfirm title="Удалить работу?" onConfirm={() => deleteTaskMutation.mutate(task.id)} okText="Удалить" cancelText="Отмена">
                  <Button type="text" size="small" danger>
                    <DeleteOutlined />
                  </Button>
                </Popconfirm>
              )}
              <TaskStatusBadge value={task.task_status} />
              {transitions.map((s) => (
                <Button key={s} size="small" onClick={() => statusMutation.mutate({ taskId: task.id, status: s })}>
                  {TASK_STATUS_LABELS[s]}
                </Button>
              ))}
              {deleted.length > 0 && <DepBadge kind="deleted" names={deleted.map((d) => d.dep_name)} />}
              {cancelled.length > 0 && <DepBadge kind="cancelled" names={cancelled.map((d) => d.dep_name)} />}
              {pending.length > 0 && <DepBadge kind="pending" names={pending.map((d) => d.dep_name)} />}
            </div>
            {task.description && (
              <div
                style={{ marginTop: 4, padding: '5px 8px', border: `1px solid ${token.colorBorder}`, borderRadius: 2, background: token.colorFillTertiary, fontSize: '0.85rem', color: token.colorTextSecondary, whiteSpace: 'pre-wrap' }}
              >
                {linkify(task.description)}
              </div>
            )}
          </div>
        );
      },
    };

    const dateColumns: TableColumnsType<Task> = dates.map((d) => {
      const dateStr = d.format(API_DATE_FORMAT);
      const isWeekend = d.day() === 0 || d.day() === 6;
      const isToday = dateStr === today;
      const isFreeze = freezeDays.has(dateStr);
      const headerTint = getHeaderTint(token, { isToday, isFreeze, isWeekend });
      const cellTint = getCellTint(token, { isToday, isFreeze, isWeekend });
      return {
        title: d.format(DISPLAY_DATE_SHORT_FORMAT),
        key: dateStr,
        width: 96,
        onHeaderCell: () => ({
          style: { ...headerTint, fontFamily: "'JetBrains Mono Variable', monospace" },
        }),
        onCell: (task) => ({
          'data-schedule-cell': true,
          'data-task-id': task.id,
          'data-date': dateStr,
          style: {
            ...cellTint,
            padding: 3,
            borderLeft: `1px solid ${token.colorBorder}`,
            cursor: task.task_status === 'done' || task.task_status === 'cancelled' ? 'not-allowed' : 'pointer',
          },
          onClick: () => {
            if (chipDragSuppressRef.current || panSuppressRef.current) return;
            if (task.task_status === 'done' || task.task_status === 'cancelled') return;
            const assignment = assignmentByKey.get(`${task.id}-${dateStr}`) ?? null;
            setAssignmentModal({ open: true, task, date: dateStr, assignment });
          },
        }),
        render: (_, task) => {
          const assignment = assignmentByKey.get(`${task.id}-${dateStr}`);
          const isTerminal = task.task_status === 'done' || task.task_status === 'cancelled';
          return assignment ? <ScheduleChip assignment={assignment} draggable={!isTerminal} /> : null;
        },
      };
    });

    return [infoColumn, ...dateColumns];
  }, [dates, assignmentByKey, depsByTask, today, token, freezeDays]);

  if (teamId === undefined) {
    return (
      <>
        <Typography.Title level={2}>Планирование</Typography.Title>
        <Card>
          <Select style={{ minWidth: 260 }} placeholder="-- Выберите команду --" onChange={handleTeamSelect} options={teams?.map((t) => ({ value: t.id, label: t.name }))} />
        </Card>
        <div style={{ marginTop: 24 }}>
          <Empty description="Выберите команду для начала планирования" />
        </div>
      </>
    );
  }

  const statusCounts = { new: 0, planned: 0 };
  const critCounts = { high: 0, medium: 0, low: 0 };
  (todayActive ?? []).forEach((a) => {
    if (a.status in statusCounts) statusCounts[a.status as keyof typeof statusCounts]++;
    if (a.criticality in critCounts) critCounts[a.criticality as keyof typeof critCounts]++;
  });

  return (
    <>
      <Typography.Title level={2}>Планирование</Typography.Title>

      <Card style={{ marginBottom: 16 }}>
        <Select style={{ minWidth: 260 }} value={teamId} onChange={handleTeamSelect} options={teams?.map((t) => ({ value: t.id, label: t.name }))} />
      </Card>

      <Card style={{ marginBottom: 16 }}>
        <Typography.Title level={5} style={{ marginTop: 0 }}>
          Фильтры
        </Typography.Title>
        <FilterGrid isMobile={isMobile}>
          <FilterField label="ПЕРИОД" isMobile={isMobile} mobileSpan={2}>
            <DatePicker.RangePicker
              value={range}
              onChange={(dates) => {
                pendingCenterRef.current = true;
                handleRangeChange(dates);
              }}
              format={DISPLAY_DATE_FORMAT}
              minDate={dayjs('2000-01-01')}
              maxDate={dayjs('2099-12-31')}
              allowClear={false}
              style={isMobile ? { width: '100%' } : undefined}
            />
          </FilterField>
          <FilterField label="ПОИСК ПО ОПИСАНИЮ" isMobile={isMobile}>
            <Input.Search
              style={{ width: isMobile ? '100%' : 220 }}
              placeholder="Введите текст..."
              allowClear
              value={search}
              onChange={(e) => {
                pendingCenterRef.current = true;
                setSearch(e.target.value);
              }}
            />
          </FilterField>
          <FilterField label="КРИТИЧНОСТЬ" isMobile={isMobile}>
            <Select mode="multiple" style={{ width: isMobile ? '100%' : 180 }} placeholder="Все" value={critFilter} onChange={setCritFilter} options={CRITICALITY_OPTIONS} />
          </FilterField>
          <FilterField label="СТАТУС" isMobile={isMobile}>
            <Select mode="multiple" style={{ width: isMobile ? '100%' : 180 }} placeholder="Все" value={statusFilter} onChange={setStatusFilter} options={ASSIGNMENT_STATUS_OPTIONS} />
          </FilterField>
          <FilterField label="СТАТУС РАБОТЫ" isMobile={isMobile}>
            <Select mode="multiple" style={{ width: isMobile ? '100%' : 180 }} placeholder="Все" value={taskStatusFilter} onChange={setTaskStatusFilter} options={TASK_STATUS_OPTIONS} />
          </FilterField>
          <FilterField isMobile={isMobile} mobileSpan="full">
            <div style={{ display: 'flex', alignItems: 'center', height: '100%' }}>
              <Checkbox
                checked={showCompleted}
                onChange={(e) => {
                  pendingCenterRef.current = true;
                  setShowCompleted(e.target.checked);
                }}
              >
                Показать завершённые
              </Checkbox>
            </div>
          </FilterField>
        </FilterGrid>
      </Card>

      <Space size={8} wrap style={{ marginBottom: 14 }}>
        <StatTile label="На сегодня" value={todayActive?.length ?? 0} primary />
        <StatGroupLabel>Статус</StatGroupLabel>
        <StatTile label="Новый" value={statusCounts.new} accent="#1668dc" />
        <StatTile label="Запланировано" value={statusCounts.planned} accent="#d89614" />
        <StatGroupLabel>Критичность</StatGroupLabel>
        <StatTile label="Высокая" value={critCounts.high} accent="#d32029" />
        <StatTile label="Средняя" value={critCounts.medium} accent="#d89614" />
        <StatTile label="Низкая" value={critCounts.low} accent="#49aa19" />
      </Space>

      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <Button type="primary" onClick={() => setTaskModal({ open: true, task: null })}>
            Добавить работу
          </Button>
          <span style={{ fontFamily: "'JetBrains Mono Variable', monospace", color: token.colorTextSecondary, fontSize: '0.9rem' }}>
            Всего работ: {taskData?.total ?? 0} | Отображено: {filteredTasks.length}
          </span>
        </div>

        {filteredTasks.length === 0 ? (
          <Empty description="Нет запланированных работ" />
        ) : (
          <div data-planning-grid style={{ cursor: 'grab' }}>
            <Table
              rowKey="id"
              columns={columns}
              dataSource={filteredTasks}
              pagination={false}
              size="small"
              scroll={{ x: 'max-content' }}
              sticky={{ offsetHeader: isMobile ? TOP_BAR_HEIGHT : 0 }}
            />
          </div>
        )}

        {taskData && taskData.total > PAGE_SIZE && (
          <div style={{ textAlign: 'center', marginTop: 16 }}>
            <Pagination
              current={page}
              pageSize={PAGE_SIZE}
              total={taskData.total}
              onChange={(p) => {
                pendingCenterRef.current = true;
                setPage(p);
              }}
              showSizeChanger={false}
            />
          </div>
        )}
      </Card>

      <TaskModal
        open={taskModal.open}
        teamId={teamId}
        task={taskModal.task}
        existingDepIds={taskModal.task ? (depsByTask.get(taskModal.task.id) ?? []).map((d) => d.dep_id) : []}
        onClose={() => setTaskModal({ open: false, task: null })}
        onDeleted={triggerCenterOnNextLoad}
      />
      <AssignmentModal
        open={assignmentModal.open}
        teamId={teamId}
        task={assignmentModal.task}
        date={assignmentModal.date}
        assignment={assignmentModal.assignment}
        taskAssignments={assignmentModal.task ? (assignmentsByTask.get(assignmentModal.task.id) ?? jumpAssignments ?? []) : []}
        freezeDays={freezeDays}
        onDeleted={triggerCenterOnNextLoad}
        onClose={() => setAssignmentModal({ open: false, task: null, date: null, assignment: null })}
      />
    </>
  );
}
