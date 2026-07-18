import {type CSSProperties, useMemo} from 'react';
import {
  Alert,
  Button,
  DatePicker,
  Form,
  Input,
  message,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  theme,
  TimePicker
} from 'antd';
import {useMutation, useQueryClient} from '@tanstack/react-query';
import dayjs from 'dayjs';
import type {Assignment, Task} from '../../hooks/usePlanningData';
import {type BlockTemplateEntry, useTeamBlocks, useTeamTemplates} from '../../hooks/usePlanningData';
import {useTeamAssignees} from '../../hooks/useSettingsData';
import {useMe} from '../../hooks/useMe';
import {formatDisplayName} from '../../hooks/useUserNames';
import {apiMutate} from '../../lib/apiMutate';
import {invalidateAssignmentData} from '../../lib/queryInvalidation';
import {useDeleteAssignmentMutation, useSaveAssignmentMutation} from './assignmentMutations';
import type {AssignmentStatus} from '../../domain/types';
import {getAutoScheduleDateRange} from '../../lib/autoSchedule';
import {API_DATE_FORMAT, DISPLAY_DATE_FORMAT, DISPLAY_DATE_SHORT_FORMAT, TIME_FORMAT} from '../../lib/dateFormats';
import {HistoryPanel, HistoryToggleButton, useHistoryToggle} from './HistoryPanel';
import {useIsMobile} from '../../hooks/useIsMobile';
import {useAutoScheduleDragScroll} from './useAutoScheduleDragScroll';
import {getCellTint, getHeaderTint} from './cellTint';
import {useAssignmentModalState} from './useAssignmentModalState';

export interface AssignmentFormValues {
  date: dayjs.Dayjs;
  time_spent: dayjs.Dayjs | null;
  block_ids: number[];
  status: AssignmentStatus;
  user_id: number | null;
  comment: string;
}

const STATUS_OPTIONS = [
  { value: 'new', label: 'Новый' },
  { value: 'planned', label: 'Запланировано' },
  { value: 'rollback', label: 'Откат' },
  { value: 'success', label: 'Успешно' },
  { value: 'cancelled', label: 'Отменено' },
];

function confirmOverwrite(dates: string[]): Promise<boolean> {
  return new Promise((resolve) => {
    Modal.confirm({
      title: 'Даты уже заняты',
      content: `На дату(ы) ${dates.join(', ')} уже есть назначение(я). Перезаписать их?`,
      okText: 'Перезаписать',
      cancelText: 'Отмена',
      onOk: () => resolve(true),
      onCancel: () => resolve(false),
    });
  });
}

function AutoScheduleGrid({
  templateBlocks,
  autoAssignDates,
  baseDate,
  freezeDays,
  taskAssignments,
  currentAssignmentId,
  selected,
  onPick,
  onPlace,
}: {
  templateBlocks: BlockTemplateEntry[];
  autoAssignDates: Record<number, string>;
  baseDate: string;
  freezeDays: Set<string>;
  taskAssignments: Assignment[];
  currentAssignmentId: number | null;
  selected: number | null;
  onPick: (blockId: number) => void;
  onPlace: (dateStr: string) => void;
}) {
  const { token } = theme.useToken();
  const dates = getAutoScheduleDateRange(baseDate, autoAssignDates);
  const today = dayjs().format(API_DATE_FORMAT);
  const dragRef = useAutoScheduleDragScroll<HTMLDivElement>();

  const headerCellBase: CSSProperties = {
    position: 'relative',
    padding: `${token.paddingXS}px ${token.paddingXS}px`,
    textAlign: 'left',
    color: token.colorTextHeading,
    fontWeight: token.fontWeightStrong,
    background: token.colorFillAlter,
    borderBottom: `1px solid ${token.colorBorderSecondary}`,
  };
  const headerSplitStyle: CSSProperties = {
    position: 'absolute',
    top: '50%',
    insetInlineEnd: 0,
    width: 1,
    height: '1.6em',
    backgroundColor: token.colorBorderSecondary,
    transform: 'translateY(-50%)',
  };
  const bodyCellBase: CSSProperties = {
    padding: `${token.paddingXS}px ${token.paddingXS}px`,
    borderBottom: `1px solid ${token.colorBorderSecondary}`,
  };
  const fixedColStyle: CSSProperties = {
    position: 'sticky',
    left: 0,
    borderRight: `1px solid ${token.colorBorderSecondary}`,
  };
  const opaqueHeaderBg = `linear-gradient(${token.colorFillAlter}, ${token.colorFillAlter}), linear-gradient(${token.colorBgContainer}, ${token.colorBgContainer})`;

  return (
    <div ref={dragRef} style={{ overflowX: 'auto', border: `1px solid ${token.colorBorder}`, borderRadius: token.borderRadiusSM }}>
      <table style={{ borderCollapse: 'collapse', width: 'max-content', fontSize: token.fontSize }}>
        <thead>
          <tr>
            <th style={{ ...headerCellBase, ...fixedColStyle, zIndex: 2, background: undefined, backgroundImage: opaqueHeaderBg }}>
              Дата
              {dates.length > 0 && <span style={headerSplitStyle} />}
            </th>
            {dates.map((dateStr, i) => {
              const d = dayjs(dateStr);
              const isWeekend = d.day() === 0 || d.day() === 6;
              const isFreeze = freezeDays.has(dateStr);
              const isToday = dateStr === today;
              const headerTint = getHeaderTint(token, { isToday, isFreeze, isWeekend });
              return (
                <th
                  key={dateStr}
                  style={{
                    ...headerCellBase,
                    minWidth: 56,
                    fontFamily: "'JetBrains Mono Variable', monospace",
                    ...headerTint,
                  }}
                >
                  {d.format(DISPLAY_DATE_SHORT_FORMAT)}
                  {i < dates.length - 1 && <span style={headerSplitStyle} />}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          <tr>
            <td style={{ ...bodyCellBase, ...fixedColStyle, zIndex: 1, background: token.colorBgContainer, fontWeight: token.fontWeightStrong }}>Блок</td>
            {dates.map((dateStr) => {
              const isOccupied = taskAssignments.some((a) => a.date === dateStr && a.id !== currentAssignmentId);
              const blocksHere = templateBlocks.filter((b) => autoAssignDates[b.id] === dateStr);
              const d = dayjs(dateStr);
              const cellTint = getCellTint(token, {
                isToday: dateStr === today,
                isFreeze: freezeDays.has(dateStr),
                isWeekend: d.day() === 0 || d.day() === 6,
              });
              return (
                <td
                  key={dateStr}
                  onClick={() => onPlace(dateStr)}
                  style={{
                    ...bodyCellBase,
                    ...cellTint,
                    height: 58,
                    verticalAlign: 'top',
                    cursor: 'pointer',
                    borderLeft: `1px solid ${token.colorBorder}`,
                    boxShadow: isOccupied ? `inset 0 0 0 2px ${token.colorWarning}` : undefined,
                  }}
                >
                  {blocksHere.map((b) => (
                    <span
                      key={b.id}
                      onClick={(e) => {
                        e.stopPropagation();
                        onPick(b.id);
                      }}
                      style={{
                        display: 'inline-block',
                        background: selected === b.id ? token.colorWarning : token.colorPrimary,
                        color: '#fff',
                        borderRadius: 3,
                        padding: '2px 6px',
                        margin: 2,
                        fontSize: '0.75rem',
                        cursor: 'pointer',
                      }}
                    >
                      {b.name}
                    </span>
                  ))}
                </td>
              );
            })}
          </tr>
        </tbody>
      </table>
    </div>
  );
}

export function AssignmentModal({
  open,
  teamId,
  task,
  date,
  assignment,
  taskAssignments,
  freezeDays,
  onClose,
}: {
  open: boolean;
  teamId: number;
  task: Task | null;
  date: string | null;
  assignment: Assignment | null;
  taskAssignments: Assignment[];
  freezeDays: Set<string>;
  onClose: () => void;
}) {
  const [form] = Form.useForm<AssignmentFormValues>();
  const queryClient = useQueryClient();
  const isMobile = useIsMobile();
  const { token } = theme.useToken();
  const { data: teamBlocks } = useTeamBlocks(teamId, task?.segment_id);
  const { data: users } = useTeamAssignees(teamId);
  const { data: allTeamTemplates } = useTeamTemplates(teamId);
  // Шаблоны команды сужаются до сегмента задачи — назначение/автопланирование должно предлагать
  // только шаблоны, относящиеся к тому же сегменту работ, что и сама задача (см. design.md).
  // useMemo сохраняет стабильную ссылку на массив между рендерами (иначе .filter() создавал бы
  // новый массив каждый раз, что зациклило бы recomputeSchedule-эффект ниже через его deps).
  const templates = useMemo(
    () => allTeamTemplates?.filter((t) => t.segment_id === task?.segment_id),
    [allTeamTemplates, task?.segment_id]
  );

  const {
    autoAssignEnabled, selectedTemplateId, autoAssignDates, autoAssignSelected, watchedDate,
    setSelectedTemplateId, setAutoAssignDates, setAutoAssignSelected, recomputeSchedule, handleAutoAssignToggle,
  } = useAssignmentModalState({open, assignment, date, teamBlocks, templates, freezeDays, form});

  const saveMutation = useSaveAssignmentMutation({includeTasks: true, successMessage: 'Сохранено', onSuccess: onClose});

  function saveAssignment(values: AssignmentFormValues) {
    if (!task) return;
    const blockNames = (values.block_ids ?? [])
      .map((id) => teamBlocks?.find((b) => b.id === id)?.name)
      .filter(Boolean)
      .join(', ');
    const timeSpent = values.time_spent ? values.time_spent.format(TIME_FORMAT) : null;
    saveMutation.mutate({
      assignment_id: assignment?.id,
      task_id: task.id,
      date: values.date.format(API_DATE_FORMAT),
      block: blockNames || null,
      status: values.status,
      user_id: values.user_id,
      comment: values.comment || null,
      time_spent: timeSpent === '00:00' ? null : timeSpent,
    });
  }

  const autoSaveMutation = useMutation({
    mutationFn: async (values: AssignmentFormValues) => {
      if (!selectedTemplateId) throw new Error('Выберите шаблон для автоназначения');
      const blocks = templates?.find((t) => t.id === selectedTemplateId)?.blocks ?? [];
      if (blocks.length === 0) throw new Error('В выбранном шаблоне нет блоков');

      const groups: Record<string, string[]> = {};
      blocks.forEach((b) => {
        const d = autoAssignDates[b.id];
        if (!d) return;
        (groups[d] ??= []).push(b.name);
      });
      const dates = Object.keys(groups).sort();
      if (dates.length === 0) throw new Error('Нет блоков для автоназначения');

      const conflictDates = dates.filter((d) => taskAssignments.some((a) => a.date === d && a.id !== assignment?.id));
      if (conflictDates.length > 0) {
        const proceed = await confirmOverwrite(conflictDates);
        if (!proceed) return { cancelled: true };
      }

      const timeSpent = values.time_spent ? values.time_spent.format(TIME_FORMAT) : null;
      await Promise.all(
        dates.map((d) => {
          const existing = taskAssignments.find((a) => a.date === d);
          return apiMutate('/api/assignment', 'POST', {
            assignment_id: existing?.id ?? null,
            task_id: task?.id,
            date: d,
            block: groups[d].join(', '),
            status: 'new',
            user_id: null,
            comment: null,
            time_spent: timeSpent === '00:00' ? null : timeSpent,
          });
        }),
      );
      return { cancelled: false };
    },
    onSuccess: (result) => {
      if (result.cancelled) return;
      invalidateAssignmentData(queryClient, true);
      message.success('Сохранено');
      onClose();
    },
    onError: (e: Error) => message.error(e.message),
  });

  const deleteMutation = useDeleteAssignmentMutation({
    onSuccess: () => {
      message.success('Назначение удалено');
      onClose();
    },
  });

  const autoAssignMissingTemplate = autoAssignEnabled && !selectedTemplateId;
  const isTerminal = task ? task.task_status === 'done' || task.task_status === 'cancelled' : false;
  const { data: me } = useMe();
  const isUser = me?.role === 'user';
  const readOnly = isTerminal || (isUser && !!assignment && assignment.status !== 'new');
  const [historyOpen, setHistoryOpen] = useHistoryToggle(open, false);
  const isSaving = saveMutation.isPending || autoSaveMutation.isPending;
  const selectedTemplateBlocks = templates?.find((t) => t.id === selectedTemplateId)?.blocks ?? [];

  // Только пользователи с is_assignee могут быть исполнителями — но если у назначения уже стоит
  // пользователь, у которого этот флаг с тех пор сняли, оставляем его в списке, иначе выбор
  // выглядел бы пустым/нерабочим при редактировании существующего назначения.
  const eligibleUsers = users?.filter((u) => u.is_assignee) ?? [];
  const currentUserId = assignment?.user_id ?? null;
  if (currentUserId !== null && !eligibleUsers.some((u) => u.id === currentUserId)) {
    const current = users?.find((u) => u.id === currentUserId);
    if (current) eligibleUsers.push(current);
  }
  const assigneeOptions = eligibleUsers.map((u) => ({ value: u.id, label: formatDisplayName(u) }));

  return (
    <Modal
      title={task ? `Работа: ${task.name}` : 'Работа'}
      open={open}
      onCancel={onClose}
      width={isMobile ? '95%' : (autoAssignEnabled ? 640 : 520) + (historyOpen ? 320 : 0)}
      footer={
        <Space>
          {assignment && <HistoryToggleButton open={historyOpen} onClick={() => setHistoryOpen((v) => !v)} />}
          {assignment && !readOnly && (
            <Popconfirm title="Удалить эту запись?" onConfirm={() => assignment && deleteMutation.mutate(assignment.id)} okText="Удалить" cancelText="Отмена">
              <Button danger loading={deleteMutation.isPending}>
                Удалить
              </Button>
            </Popconfirm>
          )}
          {!readOnly && (
            <Button type="primary" onClick={() => form.submit()} loading={isSaving} disabled={autoAssignMissingTemplate}>
              {assignment ? 'Обновить' : 'Создать'}
            </Button>
          )}
        </Space>
      }
    >
      <div style={{ display: 'flex', flexDirection: isMobile ? 'column' : 'row' }}>
      <Form form={form} layout="vertical" disabled={readOnly} onFinish={(v) => (autoAssignEnabled ? autoSaveMutation.mutate(v) : saveAssignment(v))} style={{ flex: 1, minWidth: 0 }}>
        <Space.Compact block>
          <Form.Item name="date" label="Дата" style={{ flex: 1 }} rules={[{ required: true }]}>
            <DatePicker style={{ width: '100%' }} format={DISPLAY_DATE_FORMAT} minDate={dayjs('2000-01-01')} maxDate={dayjs('2099-12-31')} allowClear={false} />
          </Form.Item>
          <Form.Item name="time_spent" label="Затраченное время" style={{ flex: 1 }}>
            <TimePicker style={{ width: '100%' }} format={TIME_FORMAT} allowClear />
          </Form.Item>
        </Space.Compact>

        {watchedDate && freezeDays.has(watchedDate.format(API_DATE_FORMAT)) && (
          <Alert type="error" showIcon title="Эта дата — день фриза, изменения в этот день не выкатываются" style={{ marginBottom: 16 }} />
        )}

        <div style={{ display: 'flex', gap: 24, marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span>Автоназначение</span>
            <Switch checked={autoAssignEnabled} onChange={handleAutoAssignToggle} />
          </div>
        </div>

        {!autoAssignEnabled && (
          <Form.Item name="block_ids" label="Блок">
            <Select mode="multiple" showSearch={{optionFilterProp: "label"}} placeholder="Поиск блока..." options={teamBlocks?.map((b) => ({ value: b.id, label: b.name }))} />
          </Form.Item>
        )}

        {autoAssignEnabled && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ marginBottom: 8 }}>
              <div style={{ fontSize: '0.8rem', marginBottom: 4 }}>Автораспределение по графику</div>
              <Select
                style={{ width: '100%' }}
                status={autoAssignMissingTemplate ? 'error' : undefined}
                showSearch={{ optionFilterProp: 'label' }}
                placeholder="— выберите шаблон —"
                value={selectedTemplateId ?? undefined}
                onChange={(v) => {
                  setSelectedTemplateId(v);
                  setAutoAssignSelected(null);
                  recomputeSchedule(v, (watchedDate ?? dayjs()).format(API_DATE_FORMAT));
                }}
                options={templates?.map((t) => ({ value: t.id, label: t.name }))}
              />
              {autoAssignMissingTemplate && (
                <div style={{ color: token.colorError, fontSize: '0.75rem', marginTop: 4 }}>Выберите график раскатки</div>
              )}
            </div>
            {selectedTemplateId && watchedDate && (
              <>
                <AutoScheduleGrid
                  templateBlocks={selectedTemplateBlocks}
                  autoAssignDates={autoAssignDates}
                  baseDate={watchedDate.format(API_DATE_FORMAT)}
                  freezeDays={freezeDays}
                  taskAssignments={taskAssignments}
                  currentAssignmentId={assignment?.id ?? null}
                  selected={autoAssignSelected}
                  onPick={(id) => setAutoAssignSelected((prev) => (prev === id ? null : id))}
                  onPlace={(d) => {
                    if (autoAssignSelected === null) return;
                    setAutoAssignDates((prev) => ({ ...prev, [autoAssignSelected]: d }));
                    setAutoAssignSelected(null);
                  }}
                />
                <div style={{ marginTop: 6, fontSize: '0.8rem', opacity: 0.7 }}>Нажмите на блок, затем на нужную дату — блок переместится туда.</div>
              </>
            )}
          </div>
        )}

        <Form.Item name="status" label="Статус">
          <Select disabled={autoAssignEnabled || isUser} options={STATUS_OPTIONS} />
        </Form.Item>

        {!autoAssignEnabled && (
          <>
            <Form.Item name="user_id" label="Исполнитель">
              <Select
                allowClear
                showSearch={{ optionFilterProp: 'label' }}
                placeholder="Не выбран"
                options={assigneeOptions}
              />
            </Form.Item>
            <Form.Item name="comment" label="Комментарий">
              <Input maxLength={45} placeholder="Комментарий..." />
            </Form.Item>
          </>
        )}
      </Form>
      <HistoryPanel kind="assignment" entityId={assignment?.id ?? null} open={historyOpen} />
      </div>
    </Modal>
  );
}
