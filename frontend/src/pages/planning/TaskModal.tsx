import {useEffect, useState} from 'react';
import {Button, Checkbox, Form, Input, Modal, Popconfirm, Select, Space, theme} from 'antd';
import {useActiveTasksList} from '../../hooks/usePlanningData';
import {useMe} from '../../hooks/useMe';
import {useDebouncedValue} from '../../hooks/useDebouncedValue';
import {useSegments} from '../../hooks/useSettingsData';
import {CriticalityBadge, TaskStatusBadge, tintedStyle} from '../../components/planningBadges';
import {linkify} from '../../lib/linkify';
import {CRITICALITY_LABELS, type Task} from '../../domain/types';
import {HistoryPanel, HistoryToggleButton, useHistoryToggle} from './HistoryPanel';
import {useIsMobile} from '../../hooks/useIsMobile';
import {useDeleteTaskMutation, useSaveTaskMutation} from '../../hooks/useTaskMutations';

interface TaskFormValues {
  name: string;
  description: string;
  criticality: string;
  segment_id: number;
}

const CRITICALITY_ORDER = ['low', 'medium', 'high'] as const;
const TERMINAL_STATUS_LABEL: Record<string, string> = {done: 'Выполнена', cancelled: 'Отменена'};

export function TaskModal({
                            open,
                            teamId,
                            task,
                            existingDepIds,
                            onClose,
                          }: {
  open: boolean;
  teamId: number;
  task: Task | null;
  existingDepIds: number[];
  onClose: () => void;
}) {
  const [form] = Form.useForm<TaskFormValues>();
  const [depIds, setDepIds] = useState<Set<number>>(new Set());
  const [depSearch, setDepSearch] = useState('');
  const debouncedDepSearch = useDebouncedValue(depSearch, 500);
  const {
    data: activeTasks,
    isLoading: depsLoading
  } = useActiveTasksList(teamId, depSearch ? debouncedDepSearch : '', existingDepIds);
  const {data: segments} = useSegments();
  const isTerminal = task ? task.task_status === 'done' || task.task_status === 'cancelled' : false;
  const {data: me} = useMe();
  const isUser = me?.role === 'user';
  const canDelete = !!task && !isTerminal && !(isUser && task.has_active_assignments);
  const [historyOpen, setHistoryOpen] = useHistoryToggle(open, isTerminal);
  const isMobile = useIsMobile();
  const {token} = theme.useToken();

  useEffect(() => {
    if (!open) return;
    form.setFieldsValue({
      name: task?.name ?? '',
      description: task?.description ?? '',
      criticality: task?.criticality ?? 'medium',
      segment_id: task?.segment_id ?? segments?.[0]?.id,
    });
    setDepIds(new Set(existingDepIds));
    setDepSearch('');
  }, [open, task, existingDepIds, form, segments]);

  const saveMutation = useSaveTaskMutation(onClose);
  const deleteMutation = useDeleteTaskMutation(task?.id, onClose);

  function saveTask(values: TaskFormValues) {
    saveMutation.mutate({
        task_id: task?.id,
        team_id: teamId,
        name: values.name,
        description: values.description || null,
        criticality: values.criticality,
        segment_id: values.segment_id,
        dependency_ids: [...depIds],
    });
  }

  const filteredDeps = (activeTasks ?? [])
    .filter((t) => t.id !== task?.id)
    .sort((a, b) => Number(depIds.has(b.id)) - Number(depIds.has(a.id)));

  function toggleDep(id: number) {
    setDepIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <Modal
      title={
        task ? (
          <Space>
            {isTerminal ? 'Работа' : 'Редактирование работы'}
            {isTerminal && (
              <span style={tintedStyle(task.task_status === 'done' ? token.colorSuccess : token.colorError)}>
                {TERMINAL_STATUS_LABEL[task.task_status] ?? task.task_status}
              </span>
            )}
          </Space>
        ) : (
          'Добавить работу'
        )
      }
      open={open}
      onCancel={onClose}
      width={isMobile ? '95%' : historyOpen ? 820 : 520}
      footer={
        <Space>
          {task && <HistoryToggleButton open={historyOpen} onClick={() => setHistoryOpen((v) => !v)}/>}
          {canDelete && (
            <Popconfirm title="Удалить всю работу со всеми назначениями?" onConfirm={() => deleteMutation.mutate()}
                        okText="Удалить" cancelText="Отмена">
              <Button danger loading={deleteMutation.isPending}>
                Удалить
              </Button>
            </Popconfirm>
          )}
          {!isTerminal && (
            <Button type="primary" onClick={() => form.submit()} loading={saveMutation.isPending}>
              {task ? 'Обновить' : 'Создать'}
            </Button>
          )}
        </Space>
      }
    >
      <div style={{display: 'flex', flexDirection: isMobile ? 'column' : 'row'}}>
        <Form form={form} layout="vertical" disabled={isTerminal} onFinish={saveTask}
              style={{flex: 1, minWidth: 0}}>
          {isTerminal ? (
            <div style={{display: 'flex', flexDirection: 'column', gap: 16, marginBottom: 16}}>
              <div style={{overflowWrap: 'anywhere'}}>
                <strong>Имя:</strong> {task?.name}
              </div>
              <div>
                <div style={{marginBottom: 4}}>
                  <strong>Описание:</strong>
                </div>
                {task?.description ? (
                  <div
                    style={{
                      maxHeight: 200,
                      overflowY: 'auto',
                      padding: '5px 8px',
                      border: `1px solid ${token.colorBorder}`,
                      borderRadius: 2,
                      background: token.colorFillTertiary,
                      whiteSpace: 'pre-wrap',
                      overflowWrap: 'anywhere',
                    }}
                  >
                    {linkify(task.description)}
                  </div>
                ) : (
                  <span style={{color: token.colorTextTertiary}}>—</span>
                )}
              </div>
              <div>
                <strong>Критичность:</strong> {CRITICALITY_LABELS[task?.criticality ?? ''] ?? task?.criticality}
              </div>
              <div>
                <strong>Сегмент:</strong> {task?.segment_name}
              </div>
            </div>
          ) : (
            <>
              <Form.Item name="name" label="Имя" rules={[{required: true, message: 'Введите имя'}]}>
                <Input/>
              </Form.Item>
              <Form.Item name="description" label="Описание">
                <Input.TextArea rows={4}/>
              </Form.Item>
              <div style={{display: 'flex', gap: 12}}>
                <Form.Item name="criticality" label="Критичность"
                           rules={[{required: true, message: 'Выберите критичность'}]} style={{flex: 1, minWidth: 0}}>
                  <Select
                    options={CRITICALITY_ORDER.map((value) => ({value, label: CRITICALITY_LABELS[value]}))}
                  />
                </Form.Item>
                <Form.Item name="segment_id" label="Сегмент" rules={[{required: true, message: 'Выберите сегмент'}]}
                           style={{flex: 1, minWidth: 0}}>
                  <Select placeholder="Выберите сегмент"
                          options={segments?.map((s) => ({value: s.id, label: s.name}))}/>
                </Form.Item>
              </div>
            </>
          )}
          {!isTerminal && (
            <Form.Item label="Зависит от">
              <Input.Search placeholder="Поиск..." value={depSearch} onChange={(e) => setDepSearch(e.target.value)}
                            style={{marginBottom: 8}} allowClear/>
              <div style={{
                maxHeight: 160,
                overflowY: 'auto',
                border: '1px solid rgba(128,128,128,0.3)',
                borderRadius: 6,
                padding: '4px 8px'
              }}>
                {filteredDeps.length === 0 && (
                  <span style={{color: 'rgba(128,128,128,0.8)'}}>{depsLoading ? 'Загрузка...' : 'Нет совпадений'}</span>
                )}
                {filteredDeps.map((t) => (
                  <div key={t.id} style={{padding: '4px 0'}}>
                    <Checkbox checked={depIds.has(t.id)} onChange={() => toggleDep(t.id)}>
                      <Space size={6}>
                        <CriticalityBadge value={t.criticality}/>
                        <TaskStatusBadge value={t.task_status}/>
                        {t.name}
                      </Space>
                    </Checkbox>
                  </div>
                ))}
              </div>
            </Form.Item>
          )}
        </Form>
        <HistoryPanel kind="task" entityId={task?.id ?? null} open={historyOpen}/>
      </div>
    </Modal>
  );
}
