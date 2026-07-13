import {type HTMLAttributes, lazy, Suspense, useEffect, useMemo, useRef, useState} from 'react';
import {useLocation, useNavigate, useParams} from 'react-router-dom';
import {ApartmentOutlined} from '@ant-design/icons';
import {
  Button,
  Card,
  Checkbox,
  DatePicker,
  Empty,
  Input,
  message,
  Pagination,
  Select,
  Space,
  Table,
  theme,
  Typography
} from 'antd';
import {useMutation, useQueryClient} from '@tanstack/react-query';
import dayjs, {type Dayjs} from 'dayjs';
import {useTeams} from '../hooks/useTeams';
import {useMe} from '../hooks/useMe';
import {
  type Assignment,
  type Task,
  useAssignments,
  useTaskById,
  useTaskDeps,
  useTasks,
  useTodayActive
} from '../hooks/usePlanningData';
import {useFreezeDays, useSegments} from '../hooks/useSettingsData';
import {useDateRangeFilter} from '../hooks/useDateRangeFilter';
import {useIsMobile} from '../hooks/useIsMobile';
import {StatGroupLabel, StatTile} from '../components/StatTile';
import {FilterField, FilterGrid} from '../components/FilterGrid';
import {type DepBadgeEntry} from '../components/planningBadges';
import {TaskModal} from './planning/TaskModal';
import {AssignmentModal} from './planning/AssignmentModal';
import {useAssignmentDrag} from './planning/useAssignmentDrag';
import {useTableDragScroll} from './planning/useTableDragScroll';
import {useTaskRowDrag} from './planning/useTaskRowDrag';
import {ASSIGNMENT_STATUS_OPTIONS, usePlanningColumns} from './planning/usePlanningColumns';
import {apiMutate} from '../lib/apiMutate';
import {API_DATE_FORMAT, DISPLAY_DATE_FORMAT} from '../lib/dateFormats';
import {TASK_STATUS_LABELS} from '../lib/historyFormat';

const DependencyGraphModal = lazy(() => import('./planning/DependencyGraphModal').then((m) => ({ default: m.DependencyGraphModal })));

const STORAGE_TEAM_ID = 'selectedTeamId';
const DEFAULT_PAGE_SIZE = 20;
const PAGE_SIZE_OPTIONS = ['10', '20', '50', '100'];
// Must match TOP_BAR_HEIGHT in components/AppShell.tsx (mobile fixed top bar height).
const TOP_BAR_HEIGHT = 56;

const TASK_STATUS_OPTIONS = [
  { value: 'new', label: 'Новый' },
  { value: 'done', label: 'Выполнено' },
  { value: 'cancelled', label: 'Отменено' },
];
const CRITICALITY_OPTIONS = [
  { value: 'low', label: 'Низкая' },
  { value: 'medium', label: 'Средняя' },
  { value: 'high', label: 'Высокая' },
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
  const { data: me } = useMe();
  const isUser = me?.role === 'user';
  const { token } = theme.useToken();
  const teamId = teamIdParam ? Number(teamIdParam) : undefined;
  const isMobile = useIsMobile();

  const [range, handleRangeChange] = useDateRangeFilter(() => [dayjs().subtract(14, 'day'), dayjs().add(14, 'day')]);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [showCompleted, setShowCompleted] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [critFilter, setCritFilter] = useState<string[]>([]);
  const [statusFilter, setStatusFilter] = useState<string[]>([]);
  const [taskStatusFilter, setTaskStatusFilter] = useState<string[]>([]);
  const [segmentFilter, setSegmentFilter] = useState<number[]>([]);
  const { data: segments } = useSegments();
  const [taskModal, setTaskModal] = useState<{ open: boolean; task: Task | null }>({ open: false, task: null });
  const [depJumpTaskId, setDepJumpTaskId] = useState<number | null>(null);
  const [graphModal, setGraphModal] = useState<{ open: boolean; taskId?: number }>({ open: false });
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

  const reorderMutation = useMutation({
    mutationFn: (taskIds: number[]) => apiMutate(`/api/tasks/${teamId}/reorder`, 'PATCH', { task_ids: taskIds }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tasks'] }),
    onError: (e: Error) => message.error(e.message),
  });

  const priorityMutation = useMutation({
    mutationFn: ({ taskId, position }: { taskId: number; position: 'start' | 'end' }) =>
      apiMutate(`/api/task/${taskId}/priority`, 'PATCH', { position }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      message.success('Приоритет изменён');
    },
    onError: (e: Error) => message.error(e.message),
  });

  useTaskRowDrag({
    onDrop: (newOrder) => reorderMutation.mutate(newOrder),
    color: token.colorPrimary,
  });

  useEffect(() => {
    if (teamId !== undefined) return;
    const saved = localStorage.getItem(STORAGE_TEAM_ID);
    if (saved && saved !== '0') navigate(`/planning/${saved}`, { replace: true });
  }, [teamId, navigate]);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 500);
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    pendingCenterRef.current = true;
    setPage(1);
  }, [teamId, debouncedSearch, showCompleted]);

  const dateFrom = range[0].format(API_DATE_FORMAT);
  const dateTo = range[1].format(API_DATE_FORMAT);
  const today = dayjs().format(API_DATE_FORMAT);

  const { data: taskData } = useTasks(teamId ?? 0, (page - 1) * pageSize, pageSize, debouncedSearch, showCompleted);
  const taskIds = useMemo(() => taskData?.tasks.map((t) => t.id) ?? [], [taskData]);
  // Зависимость, на которую перешли по клику, может отсутствовать в текущей загруженной странице
  // (пагинация/фильтры) — подмешиваем её id в запрос зависимостей, чтобы модалка задачи открылась
  // с уже заполненным списком "Зависит от", а не пустым.
  const depsTaskIds = useMemo(
    () => (depJumpTaskId && !taskIds.includes(depJumpTaskId) ? [...taskIds, depJumpTaskId] : taskIds),
    [taskIds, depJumpTaskId]
  );
  const { data: assignments } = useAssignments(teamId ?? 0, dateFrom, dateTo, taskIds);
  const { data: deps } = useTaskDeps(teamId ?? 0, depsTaskIds);
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

  // Открытие задачи-зависимости, недоступной прямо на странице (другая страница пагинации,
  // отфильтрована поиском/статусом) — тот же приём "резолвить по id, затем открыть модалку",
  // что и jumpTask выше, но без перехода по роуту (мы уже на PlanningPage).
  const { data: depJumpTask, isFetched: depJumpFetched } = useTaskById(teamId ?? 0, depJumpTaskId);
  useEffect(() => {
    if (!depJumpTaskId || !depJumpFetched) return;
    if (depJumpTask) {
      setTaskModal({ open: true, task: depJumpTask });
    } else {
      message.info('Задача не найдена');
    }
    setDepJumpTaskId(null);
  }, [depJumpTaskId, depJumpTask, depJumpFetched]);

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
        user_id: existing.user_id,
        comment: existing.comment,
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

  const assignmentStatusMutation = useMutation({
    mutationFn: ({ assignmentId, status }: { assignmentId: number; status: string }) => {
      const existing = (assignments ?? []).find((a) => a.id === assignmentId);
      if (!existing) throw new Error('Назначение не найдено');
      return apiMutate('/api/assignment', 'POST', {
        assignment_id: existing.id,
        task_id: existing.task_id,
        date: existing.date,
        block: existing.block,
        status,
        user_id: existing.user_id,
        comment: existing.comment,
        time_spent: existing.time_spent,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assignments'] });
      queryClient.invalidateQueries({ queryKey: ['active-assignments'] });
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      message.success('Статус назначения обновлён');
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
      if (segmentFilter.length && !segmentFilter.includes(t.segment_id)) return false;
      if (statusFilter.length) {
        const taskAssignments = assignmentsByTask.get(t.id) ?? [];
        if (!taskAssignments.some((a) => statusFilter.includes(a.status))) return false;
      }
      return true;
    });
  }, [taskData, critFilter, taskStatusFilter, segmentFilter, statusFilter, assignmentsByTask]);

  function handleTeamSelect(value: number) {
    localStorage.setItem(STORAGE_TEAM_ID, String(value));
    pendingCenterRef.current = true;
    navigate(`/planning/${value}`);
  }

  function handleDepNavigate(dep: DepBadgeEntry) {
    const row = document.querySelector<HTMLElement>(`[data-planning-grid] .ant-table-tbody tr[data-task-row-id="${dep.id}"]`);
    if (row) {
      row.scrollIntoView({ behavior: 'smooth', block: 'center' });
      const cells = Array.from(row.querySelectorAll<HTMLElement>('td'));
      cells.forEach((cell) => {
        cell.style.setProperty('--highlight-pulse-color', token.colorPrimary);
        cell.classList.add('task-row-highlight-pulse');
      });
      window.setTimeout(() => cells.forEach((cell) => cell.classList.remove('task-row-highlight-pulse')), 1600);
      return;
    }
    setDepJumpTaskId(dep.id);
  }

  const dates = useMemo(() => dateRange(range[0], range[1]), [range]);

  const columns = usePlanningColumns({
    dates,
    assignmentByKey,
    depsByTask,
    today,
    token,
    freezeDays,
    isUser,
    chipDragSuppressRef,
    panSuppressRef,
    priorityMutation,
    statusMutation,
    assignmentStatusMutation,
    setGraphModal,
    setTaskModal,
    setAssignmentModal,
    onDepNavigate: handleDepNavigate,
  });

  if (teamId === undefined) {
    return (
      <>
        <Typography.Title level={2}>Планирование</Typography.Title>
        <Card>
          <Select style={{ minWidth: 260 }} placeholder="-- Выберите команду --" showSearch={{ optionFilterProp: 'label' }} onChange={handleTeamSelect} options={teams?.map((t) => ({ value: t.id, label: t.name }))} />
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
        <Select style={{ minWidth: 260 }} value={teamId} showSearch={{ optionFilterProp: 'label' }} onChange={handleTeamSelect} options={teams?.map((t) => ({ value: t.id, label: t.name }))} />
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
              allowClear
              style={isMobile ? { width: '100%' } : undefined}
            />
          </FilterField>
          <FilterField label="ПОИСК ПО ОПИСАНИЮ" isMobile={isMobile}>
            <Input.Search
              style={{ width: isMobile ? '100%' : 220 }}
              placeholder="Введите текст..."
              allowClear
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </FilterField>
          <FilterField label="КРИТИЧНОСТЬ" isMobile={isMobile}>
            <Select mode="multiple" style={{ width: isMobile ? '100%' : 180 }} placeholder="Все" value={critFilter} onChange={setCritFilter} options={CRITICALITY_OPTIONS} />
          </FilterField>
          <FilterField label="СЕГМЕНТ" isMobile={isMobile}>
            <Select
              mode="multiple"
              style={{ width: isMobile ? '100%' : 180 }}
              placeholder="Все"
              value={segmentFilter}
              onChange={setSegmentFilter}
              options={segments?.map((s) => ({ value: s.id, label: s.name }))}
            />
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
          <Space>
            <Button type="primary" onClick={() => setTaskModal({ open: true, task: null })}>
              Добавить работу
            </Button>
            <Button icon={<ApartmentOutlined />} onClick={() => setGraphModal({ open: true })}>
              Граф зависимостей
            </Button>
          </Space>
          <span style={{ fontFamily: "'JetBrains Mono Variable', monospace", color: token.colorTextSecondary, fontSize: '0.9rem' }}>
            Всего работ: {taskData?.total ?? 0} | Отображено: {filteredTasks.length}
          </span>
        </div>

        {filteredTasks.length === 0 ? (
          <Empty description="Нет запланированных работ" />
        ) : (
          <div data-planning-grid style={{ cursor: 'grab' }} onContextMenu={(e) => e.preventDefault()}>
            <Table
              rowKey="id"
              columns={columns}
              dataSource={filteredTasks}
              pagination={false}
              size="small"
              scroll={{ x: 'max-content' }}
              sticky={{ offsetHeader: isMobile ? TOP_BAR_HEIGHT : 0 }}
              onRow={(task) => ({ 'data-task-row-id': task.id, 'data-task-row-criticality': task.criticality }) as HTMLAttributes<HTMLElement>}
            />
          </div>
        )}

        {taskData && taskData.total > pageSize && (
          <div style={{ textAlign: 'center', marginTop: 16 }}>
            <Pagination
              current={page}
              pageSize={pageSize}
              total={taskData.total}
              pageSizeOptions={PAGE_SIZE_OPTIONS}
              showSizeChanger
              onChange={(p, size) => {
                pendingCenterRef.current = true;
                if (size !== pageSize) {
                  setPageSize(size);
                  setPage(1);
                } else {
                  setPage(p);
                }
              }}
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
        onClose={() => setAssignmentModal({ open: false, task: null, date: null, assignment: null })}
      />
      {graphModal.open && (
        <Suspense fallback={null}>
          <DependencyGraphModal
            open={graphModal.open}
            teamId={teamId}
            taskId={graphModal.taskId}
            onClose={() => setGraphModal({ open: false })}
            onNavigate={(taskId) => {
              setGraphModal({ open: false });
              setDepJumpTaskId(taskId);
            }}
          />
        </Suspense>
      )}
    </>
  );
}
