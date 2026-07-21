import {
  type Dispatch,
  type MouseEvent as ReactMouseEvent,
  type ReactNode,
  type SetStateAction,
  useEffect,
  useMemo,
  useRef,
  useState
} from 'react';
import type {Dayjs} from 'dayjs';
import type {MenuProps, TableColumnsType} from 'antd';
import {Button, Dropdown, Modal, theme} from 'antd';
import {
  ApartmentOutlined,
  CalendarOutlined,
  CheckCircleOutlined,
  CheckOutlined,
  CloseCircleOutlined,
  CloseOutlined,
  EditOutlined,
  HolderOutlined,
  InfoCircleOutlined,
  PlusCircleOutlined,
  UndoOutlined,
  VerticalAlignBottomOutlined,
  VerticalAlignTopOutlined,
} from '@ant-design/icons';
import type {Assignment, Task, TaskDep} from '../../hooks/usePlanningData';
import type {AssignmentStatus} from '../../domain/types';
import {ASSIGNMENT_STATUS_LABELS, TASK_STATUS_LABELS} from '../../domain/types';
import {CriticalityBadge, DepBadge, type DepBadgeEntry, ScheduleChip} from '../../components/planningBadges';
import {linkify} from '../../lib/linkify';
import {API_DATE_FORMAT, DISPLAY_DATE_SHORT_FORMAT} from '../../lib/dateFormats';
import {NAME_COLUMN_WIDTH} from '../../lib/layout';
import {getCellTint, getHeaderTint} from './cellTint';
import taskTransitionsJson from '../../data/taskTransitions.json';

// Единственный источник истины — frontend/src/data/taskTransitions.json, тот же файл читает и
// support_planner.py (см. openspec/changes/shared-task-transitions-source).
const VALID_TASK_TRANSITIONS: Record<string, string[]> = taskTransitionsJson;

export const ASSIGNMENT_STATUS_OPTIONS = [
  {value: 'new', label: 'Новый'},
  {value: 'planned', label: 'Запланировано'},
  {value: 'rollback', label: 'Откат'},
  {value: 'success', label: 'Успешно'},
  {value: 'cancelled', label: 'Отменено'},
];

const ASSIGNMENT_STATUS_ICONS: Record<AssignmentStatus, ReactNode> = {
  new: <PlusCircleOutlined/>,
  planned: <CalendarOutlined/>,
  rollback: <UndoOutlined/>,
  success: <CheckCircleOutlined/>,
  cancelled: <CloseCircleOutlined/>,
};

type GlobalToken = ReturnType<typeof theme.useToken>['token'];

interface MutateFn<TVars> {
  mutate: (vars: TVars) => void;
}

interface UsePlanningColumnsOptions {
  dates: Dayjs[];
  assignmentByKey: Map<string, Assignment>;
  depsByTask: Map<number, TaskDep[] | undefined>;
  today: string;
  token: GlobalToken;
  freezeDays: Set<string>;
  isUser: boolean;
  chipDragSuppressRef: { current: boolean };
  panSuppressRef: { current: boolean };
  selectSuppressRef: { current: boolean };
  selectedAssignmentIds: Set<number>;
  onToggleAssignment: (assignmentId: number) => void;
  onClearSelection: () => void;
  priorityMutation: MutateFn<{ taskId: number; position: 'start' | 'end' }>;
  statusMutation: MutateFn<{ taskId: number; status: string }>;
  assignmentStatusMutation: MutateFn<{ assignmentId: number; status: AssignmentStatus }>;
  setGraphModal: Dispatch<SetStateAction<{ open: boolean; taskId?: number }>>;
  setTaskModal: Dispatch<SetStateAction<{ open: boolean; task: Task | null }>>;
  setAssignmentModal: Dispatch<
    SetStateAction<{ open: boolean; task: Task | null; date: string | null; assignment: Assignment | null }>
  >;
  onDepNavigate: (dep: DepBadgeEntry) => void;
}

/** Столбцы таблицы планирования — колонка "Работа" (контекстное меню статуса/приоритета,
 * бейджи зависимостей) и по одной колонке на каждую дату периода (chip назначения,
 * drag-and-drop, контекстное меню статуса назначения). Вынесено из PlanningPage.tsx как есть,
 * без изменения логики — см. openspec/changes/split-planning-page-columns. */
export function usePlanningColumns({
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
                                     onToggleAssignment,
                                     onClearSelection,
                                     priorityMutation,
                                     statusMutation,
                                     assignmentStatusMutation,
                                     setGraphModal,
                                     setTaskModal,
                                     setAssignmentModal,
                                     onDepNavigate,
                                   }: UsePlanningColumnsOptions): TableColumnsType<Task> {
  const [openContextMenu, setOpenContextMenu] = useState<string | null>(null);
  const suppressNextActivationRef = useRef(false);

  useEffect(() => {
    function suppressActivation(event: MouseEvent) {
      if (!suppressNextActivationRef.current) return;
      suppressNextActivationRef.current = false;
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
    }

    function handlePointerDown(event: PointerEvent) {
      suppressNextActivationRef.current = false;
      if (!openContextMenu) return;
      const target = event.target;
      if (!(target instanceof Element) || target.closest('.ant-dropdown')) return;

      setOpenContextMenu(null);
      suppressNextActivationRef.current = true;
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
    }

    document.addEventListener('pointerdown', handlePointerDown, true);
    document.addEventListener('click', suppressActivation, true);
    document.addEventListener('contextmenu', suppressActivation, true);
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown, true);
      document.removeEventListener('click', suppressActivation, true);
      document.removeEventListener('contextmenu', suppressActivation, true);
    };
  }, [openContextMenu]);

  return useMemo(() => {
    const infoColumn: TableColumnsType<Task>[number] = {
      title: 'Работа',
      dataIndex: 'name',
      key: 'name',
      fixed: 'left',
      width: NAME_COLUMN_WIDTH,
      onCell: (task) => {
        if (task.task_status === 'done') {
          return {style: {background: `color-mix(in srgb, ${token.colorSuccess} 16%, ${token.colorBgContainer})`}};
        }
        if (task.task_status === 'cancelled') {
          return {style: {background: `color-mix(in srgb, ${token.colorError} 16%, ${token.colorBgContainer})`}};
        }
        return {};
      },
      render: (_, task) => {
        const taskDeps = depsByTask.get(task.id) ?? [];
        const deleted = taskDeps.filter((d) => d.dep_is_deleted);
        const cancelled = taskDeps.filter((d) => !d.dep_is_deleted && d.dep_status === 'cancelled');
        const pending = taskDeps.filter((d) => !d.dep_is_deleted && d.dep_status !== 'done' && d.dep_status !== 'cancelled');
        const done = taskDeps.filter((d) => !d.dep_is_deleted && d.dep_status === 'done');
        const toDepEntry = (d: (typeof taskDeps)[number]): DepBadgeEntry => ({
          id: d.dep_id,
          name: d.dep_name,
          status: d.dep_status,
          criticality: d.dep_criticality,
          segmentName: d.dep_segment_name,
          isDeleted: !!d.dep_is_deleted,
        });
        const isTerminal = task.task_status === 'done' || task.task_status === 'cancelled';
        const transitions = isUser ? [] : (VALID_TASK_TRANSITIONS[task.task_status] ?? []);
        const menuItems: MenuProps['items'] = [
          ...(transitions.length > 0
            ? [
              {
                key: 'status-group',
                type: 'group' as const,
                label: 'Статус',
                children: transitions.map((s) => ({
                  key: s,
                  label: TASK_STATUS_LABELS[s] ?? s,
                  icon: s === 'done' ? <CheckOutlined/> : <CloseOutlined/>,
                })),
              },
            ]
            : []),
          ...(isTerminal
            ? []
            : [
              {
                key: 'priority-group',
                type: 'group' as const,
                label: 'Приоритет',
                children: [
                  {key: 'start', label: 'В начало уровня критичности', icon: <VerticalAlignTopOutlined/>},
                  {key: 'end', label: 'В конец уровня критичности', icon: <VerticalAlignBottomOutlined/>},
                ],
              },
            ]),
          {
            key: 'graph-group',
            type: 'group' as const,
            label: 'Граф',
            children: [{key: 'graph', label: 'Граф зависимостей по этой работе', icon: <ApartmentOutlined/>}],
          },
        ];

        function handleMenuClick(key: string) {
          if (key === 'start' || key === 'end') {
            priorityMutation.mutate({taskId: task.id, position: key});
            return;
          }
          if (key === 'graph') {
            setGraphModal({open: true, taskId: task.id});
            return;
          }
          if (key === 'done' || key === 'cancelled') {
            Modal.confirm({
              title: `Перевести работу в статус «${TASK_STATUS_LABELS[key]}»?`,
              okText: 'Перевести',
              cancelText: 'Отмена',
              onOk: () => statusMutation.mutate({taskId: task.id, status: key}),
            });
          }
        }

        return (
          <Dropdown
            open={openContextMenu === `task-${task.id}`}
            onOpenChange={(open) => setOpenContextMenu(open ? `task-${task.id}` : null)}
            trigger={['contextMenu']}
            menu={{items: menuItems, onClick: ({key}) => handleMenuClick(key)}}
          >
            <div title={isTerminal ? TASK_STATUS_LABELS[task.task_status] : undefined}
                 style={{maxWidth: NAME_COLUMN_WIDTH}}>
              <div style={{display: 'flex', alignItems: 'center', gap: 6}}>
                <Button
                  type="text"
                  size="small"
                  disabled={isTerminal}
                  style={{cursor: isTerminal ? 'default' : 'grab'}}
                  data-task-row-handle={isTerminal ? undefined : 'true'}
                  data-task-row-id={task.id}
                  onMouseDown={(e) => e.preventDefault()}
                  title={isTerminal ? 'Работа завершена — приоритет менять нельзя' : 'Перетащить для изменения приоритета'}
                >
                  <HolderOutlined/>
                </Button>
                <Button
                  type="text"
                  size="small"
                  onClick={() => setTaskModal({open: true, task})}
                  title={isTerminal ? 'Просмотр' : 'Редактировать'}
                >
                  {isTerminal ? <InfoCircleOutlined/> : <EditOutlined/>}
                </Button>
                <CriticalityBadge value={task.criticality}/>
                <div style={{minWidth: 0, flex: 1}}>
                  <span style={{display: 'block', fontWeight: 500, overflowWrap: 'anywhere'}}
                        data-task-row-name>{task.name}</span>
                  <div
                    data-task-row-segment
                    title={`Сегмент: ${task.segment_name}`}
                    style={{
                      marginTop: 2,
                      color: token.colorTextTertiary,
                      fontSize: '0.72rem',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    Сегмент: {task.segment_name}
                  </div>
                </div>
              </div>
              {taskDeps.length > 0 &&
                  <div style={{display: 'flex', alignItems: 'center', gap: 5, marginTop: 4, flexWrap: 'wrap'}}>
                      <span>Связи:</span>
                    {deleted.length > 0 &&
                        <DepBadge kind="deleted" deps={deleted.map(toDepEntry)} onNavigate={onDepNavigate}/>}
                    {cancelled.length > 0 &&
                        <DepBadge kind="cancelled" deps={cancelled.map(toDepEntry)} onNavigate={onDepNavigate}/>}
                    {pending.length > 0 &&
                        <DepBadge kind="pending" deps={pending.map(toDepEntry)} onNavigate={onDepNavigate}/>}
                    {done.length > 0 && <DepBadge kind="done" deps={done.map(toDepEntry)} onNavigate={onDepNavigate}/>}
                  </div>
              }
              {task.description && (
                <div
                  style={{
                    marginTop: 4,
                    padding: '5px 8px',
                    border: `1px solid ${token.colorBorder}`,
                    borderRadius: 2,
                    background: token.colorFillTertiary,
                    fontSize: '0.85rem',
                    color: token.colorTextSecondary,
                    whiteSpace: 'pre-wrap',
                    overflowWrap: 'anywhere'
                  }}
                >
                  {linkify(task.description)}
                </div>
              )}
            </div>
          </Dropdown>
        );
      },
    };

    const dateColumns: TableColumnsType<Task> = dates.map((d) => {
      const dateStr = d.format(API_DATE_FORMAT);
      const isWeekend = d.day() === 0 || d.day() === 6;
      const isToday = dateStr === today;
      const isFreeze = freezeDays.has(dateStr);
      const headerTint = getHeaderTint(token, {isToday, isFreeze, isWeekend});
      const cellTint = getCellTint(token, {isToday, isFreeze, isWeekend});
      return {
        title: d.format(DISPLAY_DATE_SHORT_FORMAT),
        key: dateStr,
        width: 96,
        onHeaderCell: () => ({
          style: {...headerTint, fontFamily: "'JetBrains Mono Variable', monospace"},
        }),
        onCell: (task) => {
          const assignment = assignmentByKey.get(`${task.id}-${dateStr}`);
          const isSelected = !!assignment && selectedAssignmentIds.has(assignment.id);
          return {
            'data-schedule-cell': true,
            'data-task-id': task.id,
            'data-date': dateStr,
            style: {
              ...cellTint,
              padding: 3,
              borderLeft: `1px solid ${token.colorBorder}`,
              cursor: task.task_status === 'done' || task.task_status === 'cancelled' ? 'not-allowed' : 'pointer',
              ...(isSelected ? {boxShadow: `inset 0 0 0 2px ${token.colorPrimary}`} : {}),
            },
            onClick: (e: ReactMouseEvent<HTMLElement>) => {
              if (chipDragSuppressRef.current || panSuppressRef.current || selectSuppressRef.current) return;
              if (task.task_status === 'done' || task.task_status === 'cancelled') return;
              const clickedAssignment = assignmentByKey.get(`${task.id}-${dateStr}`) ?? null;
              if (e.ctrlKey || e.metaKey) {
                if (clickedAssignment) onToggleAssignment(clickedAssignment.id);
                return;
              }
              if (selectedAssignmentIds.size > 0) {
                onClearSelection();
                return;
              }
              setAssignmentModal({open: true, task, date: dateStr, assignment: clickedAssignment});
            },
          };
        },
        render: (_, task) => {
          const assignment = assignmentByKey.get(`${task.id}-${dateStr}`);
          const isTerminal = task.task_status === 'done' || task.task_status === 'cancelled';
          if (!assignment) return null;
          const locked = isUser && assignment.status !== 'new';
          if (isTerminal || locked) return <ScheduleChip assignment={assignment} draggable={false}/>;
          const statusItems: MenuProps['items'] = [
            {
              key: 'status-group',
              type: 'group',
              label: 'Статус',
              children: ASSIGNMENT_STATUS_OPTIONS.filter((o) => o.value !== assignment.status).map((o) => ({
                key: o.value,
                label: ASSIGNMENT_STATUS_LABELS[o.value] ?? o.label,
                icon: ASSIGNMENT_STATUS_ICONS[o.value as AssignmentStatus],
              }))
            }
          ];
          return (
            <Dropdown
              open={openContextMenu === `assignment-${assignment.id}`}
              onOpenChange={(open) => setOpenContextMenu(open ? `assignment-${assignment.id}` : null)}
              trigger={['contextMenu']}
              menu={{
                items: statusItems,
                onClick: ({key, domEvent}) => {
                  domEvent.stopPropagation();
                  assignmentStatusMutation.mutate({assignmentId: assignment.id, status: key as AssignmentStatus});
                },
              }}
            >
              <div>
                <ScheduleChip assignment={assignment} draggable/>
              </div>
            </Dropdown>
          );
        },
      };
    });

    return [infoColumn, ...dateColumns];
  }, [dates, assignmentByKey, depsByTask, today, token, freezeDays, isUser, selectedAssignmentIds, openContextMenu]);
}
