import {type HTMLAttributes, lazy, Suspense, useCallback, useEffect, useMemo, useState} from 'react';
import {useLocation, useNavigate, useParams} from 'react-router-dom';
import {
  Alert,
  Card,
  Empty,
  Select,
  Spin,
  Table,
  theme,
  Typography
} from 'antd';
import dayjs, {type Dayjs} from 'dayjs';
import {useTeams} from '../hooks/useTeams';
import {useMe} from '../hooks/useMe';
import {
  type Assignment,
  type Task,
} from '../domain/types';
import {useFreezeDays, useSegments} from '../hooks/useSettingsData';
import {useDateRangeFilter} from '../hooks/useDateRangeFilter';
import {useIsMobile} from '../hooks/useIsMobile';
import {type DepBadgeEntry} from '../components/planningBadges';
import {TaskModal} from './planning/TaskModal';
import {AssignmentModal} from './planning/AssignmentModal';
import {
  TaskCompletionSuggestionModal,
  type TaskCompletionSuggestion,
} from './planning/TaskCompletionSuggestionModal';
import {TaskArchiveModal} from './planning/TaskArchiveModal';
import {useAssignmentDrag} from './planning/useAssignmentDrag';
import {useAssignmentSelection} from './planning/useAssignmentSelection';
import {useTableDragScroll} from './planning/useTableDragScroll';
import {useTaskRowDrag} from './planning/useTaskRowDrag';
import {usePlanningColumns} from './planning/usePlanningColumns';
import {API_DATE_FORMAT} from '../lib/dateFormats';
import {useDebouncedValue} from '../hooks/useDebouncedValue';
import {useStoredTeamRoute} from '../hooks/useStoredTeamRoute';
import {DEFAULT_PAGE_SIZE} from '../lib/pagination';
import {usePaginationState} from '../hooks/usePaginationState';
import {usePlanningFilters} from './planning/usePlanningFilters';
import {createPlanningGridViewKey, usePlanningGridTodayCenter} from './planning/usePlanningGridTodayCenter';
import {TOP_BAR_HEIGHT} from "../components/AppShell.tsx";
import {AppPagination} from '../components/AppPagination';
import {usePlanningLookups} from './planning/usePlanningLookups';
import {usePlanningNavigation} from './planning/usePlanningNavigation';
import {scrollToPlanningTaskRow, useTaskRowHighlight} from './planning/focusPlanningTask';
import {usePlanningQueries} from './planning/usePlanningQueries';
import {usePlanningSelection} from './planning/usePlanningSelection';
import {usePlanningAssignmentActions} from './planning/usePlanningAssignmentActions';
import {PlanningFiltersCard} from './planning/PlanningFiltersCard';
import {PlanningStats} from './planning/PlanningStats';
import {PlanningToolbar} from './planning/PlanningToolbar';
import {
  useTaskPriorityMutation,
  useTaskPsiStatusMutation,
  useTaskReorderMutation,
  useTaskStatusMutation,
} from '../hooks/useTaskMutations';
import {NewTasksOverviewCard} from '../components/NewTaskNotifications';

const DependencyGraphModal = lazy(() => import('./planning/DependencyGraphModal').then((m) => ({default: m.DependencyGraphModal})));

function dateRange(from: Dayjs, to: Dayjs): Dayjs[] {
  const dates: Dayjs[] = [];
  let cur = from;
  while (!cur.isAfter(to)) {
    dates.push(cur);
    cur = cur.add(1, 'day');
  }
  return dates;
}

export function PlanningPage() {
  const {teamId: teamIdParam} = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const jump = location.state as { jumpTaskId?: number; jumpDate?: string } | null;
  const {data: teams} = useTeams();
  const {data: me} = useMe();
  const isUser = me?.role === 'user';
  const {token} = theme.useToken();
  const teamId = teamIdParam ? Number(teamIdParam) : undefined;
  const isMobile = useIsMobile();
  const selectTeamRoute = useStoredTeamRoute('/planning', teamId, teams);

  const [range, handleRangeChange] = useDateRangeFilter(() => [dayjs().subtract(14, 'day'), dayjs().add(14, 'day')]);
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search, 500);
  const [showCompleted, setShowCompleted] = useState(false);
  const [archiveOpen, setArchiveOpen] = useState(false);
  const pagination = usePaginationState(DEFAULT_PAGE_SIZE);
  const {page, pageSize} = pagination;
  const {data: segments} = useSegments();
  const [taskModal, setTaskModal] = useState<{ open: boolean; task: Task | null }>({open: false, task: null});
  const [graphModal, setGraphModal] = useState<{ open: boolean; taskId?: number }>({open: false});
  const [assignmentModal, setAssignmentModal] = useState<{
    open: boolean;
    task: Task | null;
    date: string | null;
    assignment: Assignment | null
  }>({
    open: false,
    task: null,
    date: null,
    assignment: null,
  });
  const [completionSuggestion, setCompletionSuggestion] = useState<TaskCompletionSuggestion | null>(null);
  const {selectedAssignmentIds, setSelectedAssignmentIds} = usePlanningSelection({
    teamId, search: debouncedSearch, showCompleted, page, pageSize,
  });

  const {
    data: freezeDaysList,
    isPending: freezeDaysPending,
    isError: freezeDaysError,
  } = useFreezeDays();
  const freezeDays = useMemo(() => new Set(freezeDaysList ?? []), [freezeDaysList]);

  const statusMutation = useTaskStatusMutation(
    (taskId) => taskData?.tasks.find((task) => task.id === taskId)?.name,
  );
  const reorderMutation = useTaskReorderMutation(teamId);
  const priorityMutation = useTaskPriorityMutation();
  const psiStatusMutation = useTaskPsiStatusMutation();

  useTaskRowDrag({
    onDrop: (newOrder) => reorderMutation.mutate(newOrder),
    color: token.colorPrimary,
  });

  useEffect(() => {
    pagination.reset();
  }, [teamId, debouncedSearch, showCompleted, pagination.reset]);

  const dateFrom = range[0].format(API_DATE_FORMAT);
  const dateTo = range[1].format(API_DATE_FORMAT);
  const today = dayjs().format(API_DATE_FORMAT);
  const clearJump = useCallback(
    () => navigate(location.pathname, {replace: true, state: null}),
    [location.pathname, navigate],
  );
  const openJumpAssignment = useCallback(
    (task: Task, date: string, assignment: Assignment | null) =>
      setAssignmentModal({open: true, task, date, assignment}),
    [],
  );
  const openJumpTask = useCallback(
    (task: Task) => setTaskModal({open: true, task}),
    [],
  );

  const {
    depJumpTaskId,
    setDepJumpTaskId,
    jumpAssignments,
  } = usePlanningNavigation({
    teamId: teamId ?? 0,
    jump,
    clearJump,
    openAssignment: openJumpAssignment,
    openTask: openJumpTask,
  });
  const {
    taskData, taskIds, assignments, deps, todayActive, planningDataError, planningDataReady,
  } = usePlanningQueries({
    teamId: teamId ?? 0,
    offset: pagination.offset,
    pageSize,
    search: debouncedSearch,
    showCompleted,
    dateFrom,
    dateTo,
    today,
    depJumpTaskId,
    freezeDaysPending,
    freezeDaysError,
  });
  const {assignmentByKey, assignmentById, assignmentsByTask, depsByTask} =
    usePlanningLookups(assignments, deps);
  const {highlightedTaskId, highlightRevision, highlightTask} = useTaskRowHighlight();

  const {
    rescheduleMutation,
    assignmentStatusMutation,
    bulkDeleteMutation,
    bulkRescheduleMutation,
    isTaskLocked,
    isAssignmentLocked,
  } = usePlanningAssignmentActions({
    assignments,
    tasks: taskData?.tasks,
    setSelectedAssignmentIds,
    onTaskCompletionSuggested: setCompletionSuggestion,
  });

  const chipDragSuppressRef = useAssignmentDrag({
    isAssignmentLocked,
    getOccupant: (taskId, date) => assignmentByKey.get(`${taskId}-${date}`),
    onDrop: (assignmentId, _taskId, newDate) => rescheduleMutation.mutate({assignmentId, newDate}),
    onDropMany: (moves) => bulkRescheduleMutation.mutate(moves),
    colors: {success: token.colorSuccess, error: token.colorError, selected: token.colorPrimary},
    selectedAssignmentIds,
    getAssignment: (id) => assignmentById.get(id),
  });

  const panSuppressRef = useTableDragScroll({isTaskLocked});

  const selectSuppressRef = useAssignmentSelection({
    selectedAssignmentIds,
    onCommitSelection: (ids) => setSelectedAssignmentIds((prev) => new Set([...prev, ...ids])),
    color: token.colorPrimary,
  });

  const {
    criticalities: critFilter, setCriticalities: setCritFilter,
    assignmentStatuses: statusFilter, setAssignmentStatuses: setStatusFilter,
    taskStatuses: taskStatusFilter, setTaskStatuses: setTaskStatusFilter,
    segmentIds: segmentFilter, setSegmentIds: setSegmentFilter,
    filteredTasks,
  } = usePlanningFilters(taskData?.tasks, assignmentsByTask);

  const planningViewKey = createPlanningGridViewKey({
    teamId: teamId ?? 0,
    dateFrom,
    dateTo,
    search: debouncedSearch,
    showCompleted,
    page,
    pageSize,
    criticalities: critFilter,
    assignmentStatuses: statusFilter,
    taskStatuses: taskStatusFilter,
    segmentIds: segmentFilter,
    taskIds,
  });
  const planningRenderKey = filteredTasks.map((task) => task.id).join(',');
  usePlanningGridTodayCenter({
    today,
    isReady: planningDataReady,
    viewKey: planningViewKey,
    renderKey: planningRenderKey,
  });

  const focusTask = useCallback((taskId: number) => {
    if (scrollToPlanningTaskRow(taskId)) highlightTask(taskId);
    else setDepJumpTaskId(taskId);
  }, [highlightTask, setDepJumpTaskId]);

  useEffect(() => {
    if (!jump?.jumpTaskId || jump.jumpDate || !planningDataReady) return;
    focusTask(jump.jumpTaskId);
    clearJump();
  }, [jump, planningDataReady, focusTask, clearJump]);

  function handleTeamSelect(value: number) {
    selectTeamRoute(value);
  }

  function handleDepNavigate(dep: DepBadgeEntry) {
    focusTask(dep.id);
  }

  const dates = useMemo(() => dateRange(range[0], range[1]), [range]);

  const columns = usePlanningColumns({
    teamId,
    dates,
    assignmentByKey,
    depsByTask,
    today,
    token,
    freezeDays,
    isUser,
    chipDragSuppressRef,
    panSuppressRef,
    selectSuppressRef,
    selectedAssignmentIds,
    onToggleAssignment: (assignmentId) =>
      setSelectedAssignmentIds((prev) => {
        const next = new Set(prev);
        if (next.has(assignmentId)) next.delete(assignmentId);
        else next.add(assignmentId);
        return next;
      }),
    onClearSelection: () => setSelectedAssignmentIds(new Set()),
    priorityMutation,
    statusMutation,
    psiStatusMutation,
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
        <NewTasksOverviewCard/>
        <Card>
          <Select style={{minWidth: 260}} placeholder="-- Выберите команду --" showSearch={{optionFilterProp: 'label'}}
                  onChange={handleTeamSelect} options={teams?.map((t) => ({value: t.id, label: t.name}))}/>
        </Card>
        <div style={{marginTop: 24}}>
          <Empty description="Выберите команду для начала планирования"/>
        </div>
      </>
    );
  }

  return (
    <>
      <Typography.Title level={2}>Планирование</Typography.Title>
      <NewTasksOverviewCard/>

      <Card style={{marginBottom: 16}}>
        <Select style={{minWidth: 260}} value={teamId} showSearch={{optionFilterProp: 'label'}}
                onChange={handleTeamSelect} options={teams?.map((t) => ({value: t.id, label: t.name}))}/>
      </Card>

      <PlanningFiltersCard
        isMobile={isMobile}
        range={range}
        onRangeChange={handleRangeChange}
        search={search}
        setSearch={setSearch}
        criticalities={critFilter}
        setCriticalities={setCritFilter}
        segmentIds={segmentFilter}
        setSegmentIds={setSegmentFilter}
        assignmentStatuses={statusFilter}
        setAssignmentStatuses={setStatusFilter}
        taskStatuses={taskStatusFilter}
        setTaskStatuses={setTaskStatusFilter}
        segments={segments}
        showCompleted={showCompleted}
        setShowCompleted={setShowCompleted}
      />

      <PlanningStats items={todayActive}/>

      <Card>
        <PlanningToolbar
          selectedIds={selectedAssignmentIds}
          bulkDeletePending={bulkDeleteMutation.isPending}
          total={taskData?.total ?? 0}
          visible={filteredTasks.length}
          borderColor={token.colorBorder}
          secondaryTextColor={token.colorTextSecondary}
          onAdd={() => setTaskModal({open: true, task: null})}
          onGraph={() => setGraphModal({open: true})}
          onArchive={() => setArchiveOpen(true)}
          onDeleteSelected={() => bulkDeleteMutation.mutate([...selectedAssignmentIds])}
          onClearSelection={() => setSelectedAssignmentIds(new Set())}
        />

        {planningDataError ? (
          <Alert
            type="error"
            showIcon
            title="Не удалось загрузить таблицу планирования"
            description="Обновите страницу или повторите попытку позже."
          />
        ) : !planningDataReady ? (
          <div style={{display: 'flex', justifyContent: 'center', padding: '48px 0'}}>
            <Spin size="large" description="Загрузка таблицы..."/>
          </div>
        ) : filteredTasks.length === 0 ? (
          <Empty description="Нет запланированных работ"/>
        ) : (
          <div data-planning-grid style={{cursor: 'grab'}} onContextMenu={(e) => e.preventDefault()}>
            <Table
              rowKey="id"
              columns={columns}
              dataSource={filteredTasks}
              pagination={false}
              size="small"
              scroll={{x: 'max-content'}}
              sticky={{offsetHeader: isMobile ? TOP_BAR_HEIGHT : 0}}
              rowClassName={(task) => task.id === highlightedTaskId
                ? `task-row-highlight-pulse task-row-highlight-pulse-${highlightRevision % 2 ? 'a' : 'b'}` : ''}
              onRow={(task) => ({
                'data-task-row-id': task.id,
                'data-task-row-criticality': task.criticality,
                style: {'--highlight-pulse-color': token.colorPrimary},
              }) as HTMLAttributes<HTMLElement>}
            />
          </div>
        )}

        {taskData && <AppPagination current={page} pageSize={pageSize} total={taskData.total}
                                    allowPageSizeChange onChange={pagination.onChange}/>}
      </Card>

      <TaskModal
        open={taskModal.open}
        teamId={teamId}
        task={taskModal.task}
        existingDepIds={taskModal.task ? (depsByTask.get(taskModal.task.id) ?? []).map((d) => d.dep_id) : []}
        onClose={() => setTaskModal({open: false, task: null})}
      />
      <TaskArchiveModal open={archiveOpen} teamId={teamId} canRestore={!isUser}
                        onClose={() => setArchiveOpen(false)}/>
      <AssignmentModal
        open={assignmentModal.open}
        teamId={teamId}
        task={assignmentModal.task}
        date={assignmentModal.date}
        assignment={assignmentModal.assignment}
        taskAssignments={assignmentModal.task ? (assignmentsByTask.get(assignmentModal.task.id) ?? jumpAssignments ?? []) : []}
        freezeDays={freezeDays}
        onClose={() => setAssignmentModal({open: false, task: null, date: null, assignment: null})}
      />
      <TaskCompletionSuggestionModal
        suggestion={completionSuggestion}
        onCancel={() => setCompletionSuggestion(null)}
        onConfirm={(taskId) => {
          setCompletionSuggestion(null);
          statusMutation.mutate({taskId, status: 'done'});
        }}
      />
      {graphModal.open && (
        <Suspense fallback={null}>
          <DependencyGraphModal
            open={graphModal.open}
            teamId={teamId}
            taskId={graphModal.taskId}
            onClose={() => setGraphModal({open: false})}
            onNavigate={(taskId) => {
              setGraphModal({open: false});
              setDepJumpTaskId(taskId);
            }}
          />
        </Suspense>
      )}
    </>
  );
}
