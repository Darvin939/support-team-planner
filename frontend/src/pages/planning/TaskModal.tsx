import {useEffect, useState} from 'react';
import {Button, Checkbox, Form, Input, message, Modal, Popconfirm, Select, Space} from 'antd';
import {useMutation, useQueryClient} from '@tanstack/react-query';
import type {Task} from '../../hooks/usePlanningData';
import {useActiveTasksList} from '../../hooks/usePlanningData';
import {useMe} from '../../hooks/useMe';
import {useSegments} from '../../hooks/useSettingsData';
import {CriticalityBadge, TaskStatusBadge} from '../../components/planningBadges';
import {apiMutate} from '../../lib/apiMutate';
import {HistoryPanel, HistoryToggleButton, useHistoryToggle} from './HistoryPanel';
import {useIsMobile} from '../../hooks/useIsMobile';

interface TaskFormValues {
  name: string;
  description: string;
  criticality: string;
  segment_id: number;
}

export function TaskModal({
  open,
  teamId,
  task,
  existingDepIds,
  onClose,
  onDeleted,
}: {
  open: boolean;
  teamId: number;
  task: Task | null;
  existingDepIds: number[];
  onClose: () => void;
  onDeleted?: () => void;
}) {
  const [form] = Form.useForm<TaskFormValues>();
  const queryClient = useQueryClient();
  const [depIds, setDepIds] = useState<Set<number>>(new Set());
  const [depSearch, setDepSearch] = useState('');
  const [debouncedDepSearch, setDebouncedDepSearch] = useState('');
  const { data: activeTasks, isLoading: depsLoading } = useActiveTasksList(teamId, debouncedDepSearch, existingDepIds);
  const { data: segments } = useSegments();
  const isTerminal = task ? task.task_status === 'done' || task.task_status === 'cancelled' : false;
  const { data: me } = useMe();
  const isUser = me?.role === 'user';
  const canDelete = !!task && !isTerminal && !(isUser && task.has_active_assignments);
  const [historyOpen, setHistoryOpen] = useHistoryToggle(open, isTerminal);
  const isMobile = useIsMobile();

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
    setDebouncedDepSearch('');
  }, [open, task, existingDepIds, form, segments]);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedDepSearch(depSearch), 500);
    return () => clearTimeout(timer);
  }, [depSearch]);

  const saveMutation = useMutation({
    mutationFn: (values: TaskFormValues) =>
      apiMutate('/api/task', 'POST', {
        task_id: task?.id,
        team_id: teamId,
        name: values.name,
        description: values.description || null,
        criticality: values.criticality,
        segment_id: values.segment_id,
        dependency_ids: [...depIds],
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      queryClient.invalidateQueries({ queryKey: ['task-deps'] });
      message.success('Сохранено');
      onClose();
    },
    onError: (e: Error) => message.error(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: () => apiMutate(`/api/task/${task!.id}`, 'DELETE'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      message.success('Задача удалена');
      onDeleted?.();
      onClose();
    },
    onError: (e: Error) => message.error(e.message),
  });

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
      title={task ? 'Редактирование работы' : 'Добавить работу'}
      open={open}
      onCancel={onClose}
      width={isMobile ? '95%' : historyOpen ? 820 : 520}
      footer={
        <Space>
          {task && <HistoryToggleButton open={historyOpen} onClick={() => setHistoryOpen((v) => !v)} />}
          {canDelete && (
            <Popconfirm title="Удалить всю работу со всеми назначениями?" onConfirm={() => deleteMutation.mutate()} okText="Удалить" cancelText="Отмена">
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
      <div style={{ display: 'flex', flexDirection: isMobile ? 'column' : 'row' }}>
        <Form form={form} layout="vertical" disabled={isTerminal} onFinish={(v) => saveMutation.mutate(v)} style={{ flex: 1, minWidth: 0 }}>
          <Form.Item name="name" label="Имя" rules={[{ required: true, message: 'Введите имя' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label="Описание">
            <Input.TextArea rows={4} />
          </Form.Item>
          <div style={{ display: 'flex', gap: 12 }}>
            <Form.Item name="criticality" label="Критичность" rules={[{ required: true, message: 'Выберите критичность' }]} style={{ flex: 1, minWidth: 0 }}>
              <Select
                options={[
                  { value: 'low', label: 'Низкая' },
                  { value: 'medium', label: 'Средняя' },
                  { value: 'high', label: 'Высокая' },
                ]}
              />
            </Form.Item>
            <Form.Item name="segment_id" label="Сегмент" rules={[{ required: true, message: 'Выберите сегмент' }]} style={{ flex: 1, minWidth: 0 }}>
              <Select placeholder="Выберите сегмент" options={segments?.map((s) => ({ value: s.id, label: s.name }))} />
            </Form.Item>
          </div>
          <Form.Item label="Зависит от">
            <Input.Search placeholder="Поиск..." value={depSearch} onChange={(e) => setDepSearch(e.target.value)} style={{ marginBottom: 8 }} allowClear />
            <div style={{ maxHeight: 160, overflowY: 'auto', border: '1px solid rgba(128,128,128,0.3)', borderRadius: 6, padding: '4px 8px' }}>
              {filteredDeps.length === 0 && (
                <span style={{ color: 'rgba(128,128,128,0.8)' }}>{depsLoading ? 'Загрузка...' : 'Нет совпадений'}</span>
              )}
              {filteredDeps.map((t) => (
                <div key={t.id} style={{ padding: '4px 0' }}>
                  <Checkbox checked={depIds.has(t.id)} onChange={() => toggleDep(t.id)}>
                    <Space size={6}>
                      <CriticalityBadge value={t.criticality} />
                      <TaskStatusBadge value={t.task_status} />
                      {t.name}
                    </Space>
                  </Checkbox>
                </div>
              ))}
            </div>
          </Form.Item>
        </Form>
        <HistoryPanel kind="task" entityId={task?.id ?? null} open={historyOpen} />
      </div>
    </Modal>
  );
}
