import {type CSSProperties, useEffect, useState} from 'react';
import {Button, Card, Checkbox, Form, Input, Modal, Popconfirm, Select, Space, Tabs, theme} from 'antd';
import {useActiveTasksList, useTaskAssignmentTimeline, useTeamTemplates} from '../../hooks/usePlanningData';
import {useMe} from '../../hooks/useMe';
import {useDebouncedValue} from '../../hooks/useDebouncedValue';
import {useSegments} from '../../hooks/useSettingsData';
import {CriticalityBadge, TaskStatusBadge, tintedStyle} from '../../components/planningBadges';
import {linkify} from '../../lib/linkify';
import {
  type Criticality,
  CRITICALITY_LABELS,
  CRITICALITY_OPTIONS,
  PSI_STATUS_LABELS,
  type Task
} from '../../domain/types';
import {HistoryPanel} from './HistoryPanel';
import {useIsMobile} from '../../hooks/useIsMobile';
import {useDeleteTaskMutation, useSaveTaskMutation} from '../../hooks/useTaskMutations';
import type {ApiResult} from '../../lib/apiMutate';
import {AssignmentTimeline} from './assignmentTimeline';

interface TaskFormValues {
  name: string;
  description: string;
  instruction_url: string;
  criticality: Criticality;
  segment_id: number;
  completion_template_id: number | null;
  psi_required: boolean;
}

const TERMINAL_STATUS_LABEL: Record<string, string> = {done: 'Выполнена', cancelled: 'Отменена'};

export function TaskModal({
                            open,
                            teamId,
                            task,
                            existingDepIds,
                            onClose,
                            onTaskCompletionSuggested,
                          }: {
  open: boolean;
  teamId: number;
  task: Task | null;
  existingDepIds: number[];
  onClose: () => void;
  onTaskCompletionSuggested?: (result: ApiResult) => void;
}) {
  const [form] = Form.useForm<TaskFormValues>();
  const [depIds, setDepIds] = useState<Set<number>>(new Set());
  const [depSearch, setDepSearch] = useState('');
  const [activeTab, setActiveTab] = useState('main');
  const debouncedDepSearch = useDebouncedValue(depSearch, 500);
  const {
    data: activeTasks,
    isLoading: depsLoading
  } = useActiveTasksList(teamId, depSearch ? debouncedDepSearch : '', existingDepIds);
  const {data: segments} = useSegments();
  const templatesQuery = useTeamTemplates(teamId);
  const selectedSegment = Form.useWatch('segment_id', form);
  const templates = templatesQuery.data?.filter((t) => t.segment_id === selectedSegment) ?? [];
  const templateOptions = templates.map((t) => ({value: t.id, label: t.name}));
  if (task?.completion_template_id && !templates.some((t) => t.id === task.completion_template_id)
      && selectedSegment === task.segment_id) {
    templateOptions.push({value: task.completion_template_id,
      label: task.completion_template_name ?? `Шаблон #${task.completion_template_id}`});
  }
  const configurationLocked = !!task?.has_assignments;
  const isTerminal = task ? task.task_status === 'done' || task.task_status === 'cancelled' : false;
  const {data: me} = useMe();
  const isUser = me?.role === 'user';
  const canDelete = !!task && !isTerminal && !(isUser && task.has_active_assignments);
  const assignmentTimeline = useTaskAssignmentTimeline(task?.id ?? null, open && !!task);
  const isMobile = useIsMobile();
  const {token} = theme.useToken();
  const parameterGridStyle: CSSProperties = {
    display: 'grid',
    gridTemplateColumns: isMobile ? 'minmax(0, 1fr)' : 'repeat(2, minmax(0, 1fr))',
    columnGap: 16,
    rowGap: isMobile ? 12 : 0,
  };

  useEffect(() => {
    if (!open) return;
    form.resetFields();
    form.setFieldsValue({
      name: task?.name ?? '',
      description: task?.description ?? '',
      instruction_url: task?.instruction_url ?? '',
      criticality: task?.criticality ?? 'medium',
      segment_id: task?.segment_id,
      completion_template_id: task?.completion_template_id ?? null,
      psi_required: task?.psi_status === 'required' || task?.psi_status === 'passed',
    });
    setDepIds(new Set(existingDepIds));
    setDepSearch('');
    setActiveTab('main');
  }, [open, task, existingDepIds, form]);

  const saveMutation = useSaveTaskMutation((result) => {
    onTaskCompletionSuggested?.(result);
    onClose();
  });
  const deleteMutation = useDeleteTaskMutation(task?.id, onClose);

  function saveTask(values: TaskFormValues) {
    const psiStatus = task?.has_active_assignments
      ? task.psi_status
      : values.psi_required
        ? task?.psi_status === 'required' || task?.psi_status === 'passed'
          ? task.psi_status
          : 'required'
        : 'not_required';
    saveMutation.mutate({
      task_id: task?.id,
      team_id: teamId,
      name: values.name,
      description: values.description || null,
      instruction_url: values.instruction_url?.trim() || null,
      criticality: values.criticality,
      psi_status: psiStatus,
      segment_id: values.segment_id,
      completion_template_id: values.completion_template_id ?? null,
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
      width={isMobile ? '95%' : 760}
      footer={
        <Space>
          {activeTab === 'history' ? <Button onClick={onClose}>Закрыть</Button> : <>
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
          </>}
        </Space>
      }
    >
      <div style={{display: 'flex', flexDirection: isMobile ? 'column' : 'row'}}>
        <Form form={form} layout="vertical" disabled={isTerminal} onFinish={saveTask}
              style={{flex: 1, minWidth: 0}}>
          {isTerminal ? (
            <Tabs activeKey={activeTab} onChange={setActiveTab} items={[
              {key: 'main', label: 'Основное', children: (
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
              <div style={{overflowWrap: 'anywhere'}}>
                <strong>Ссылка на инструкцию:</strong>{' '}
                {task?.instruction_url ? (
                  <a href={task.instruction_url} target="_blank" rel="noopener noreferrer">
                    {task.instruction_url}
                  </a>
                ) : (
                  <span style={{color: token.colorTextTertiary}}>—</span>
                )}
              </div>
              <div>
                <strong>Критичность:</strong> {task ? CRITICALITY_LABELS[task.criticality] : '—'}
              </div>
              <div>
                <strong>Сегмент:</strong> {task?.segment_name}
              </div>
              <div><strong>Шаблон раскатки:</strong> {task?.completion_template_name ?? 'Не указан'}</div>
              <div>
                <strong>ПСИ:</strong> {task ? PSI_STATUS_LABELS[task.psi_status] : ''}
              </div>
              <div>
                <div style={{marginBottom: 8}}><strong>Назначения:</strong></div>
                <AssignmentTimeline assignments={assignmentTimeline.data} loading={assignmentTimeline.isLoading} error={assignmentTimeline.isError}/>
              </div>
            </div>
              )},
              {key: 'history', label: 'История', children: (
                <HistoryPanel kind="task" entityId={task?.id ?? null} open={activeTab === 'history'}/>
              )},
            ]}/>
          ) : (
            <Tabs
              activeKey={activeTab}
              onChange={setActiveTab}
              items={[
                {
                  key: 'main',
                  label: 'Основное',
                  children: (
                    <>
                      <Form.Item name="name" label="Имя" rules={[{required: true, message: 'Введите имя'}]}>
                        <Input/>
                      </Form.Item>
                      <Form.Item name="description" label="Описание">
                        <Input.TextArea rows={7}/>
                      </Form.Item>
                      <Form.Item
                        name="instruction_url"
                        label="Ссылка на инструкцию"
                        rules={[
                          {max: 2048, message: 'Ссылка не должна быть длиннее 2048 символов'},
                          {
                            validator: async (_, value: string | undefined) => {
                              if (!value?.trim()) return;
                              try {
                                const url = new URL(value.trim());
                                if ((url.protocol === 'http:' || url.protocol === 'https:') && url.hostname) return;
                              } catch {
                                // Единое сообщение ниже для всех невалидных URL.
                              }
                              throw new Error('Укажите полную HTTP(S)-ссылку');
                            },
                          },
                        ]}
                      >
                        <Input type="url" placeholder="https://example.com/instruction"/>
                      </Form.Item>
                      <Card size="small" role="group" aria-label="Параметры работы"
                            styles={{body: {padding: 8}}} style={{marginBottom: 8}}>
                        <div style={parameterGridStyle}>
                        <Form.Item name="criticality" label="Критичность" style={{marginBottom: 0}}
                                   rules={[{required: true, message: 'Выберите критичность'}]}>
                          <Select
                            options={CRITICALITY_OPTIONS}
                          />
                        </Form.Item>
                        <Form.Item name="psi_required" valuePropName="checked"
                                   style={{marginBottom: 0, alignSelf: 'end'}}>
                          <Checkbox disabled={task?.has_active_assignments} style={{minHeight: 32, alignItems: 'center'}}>
                            Требуется ПСИ
                          </Checkbox>
                        </Form.Item>
                        </div>
                      </Card>
                      <Card size="small" role="group" aria-label="Параметры раскатки"
                            styles={{body: {padding: 8}}} style={{marginBottom: 16}}>
                        <div style={parameterGridStyle}>
                        <Form.Item name="segment_id" label="Сегмент" style={{marginBottom: 0}}
                                   rules={[{required: true, message: 'Выберите сегмент'}]}>
                          <Select placeholder="Выберите сегмент"
                                  disabled={configurationLocked}
                                  onChange={() => form.setFieldValue('completion_template_id', null)}
                                  options={segments?.map((s) => ({value: s.id, label: s.name}))}/>
                        </Form.Item>
                        <Form.Item name="completion_template_id" label="Шаблон раскатки" style={{marginBottom: 0}}
                                   rules={[{required: !task || !!task.completion_template_id
                                     || selectedSegment !== task.segment_id, message: 'Выберите шаблон раскатки'}]}
                                   extra={templatesQuery.isError ? 'Не удалось загрузить шаблоны. Повторите открытие формы.'
                                     : !templatesQuery.isLoading && selectedSegment && templates.length === 0
                                       ? 'Для команды в этом сегменте нет доступных шаблонов' : undefined}>
                          <Select placeholder="Выберите шаблон раскатки" loading={templatesQuery.isLoading}
                                  disabled={!selectedSegment || templatesQuery.isError
                                    || (configurationLocked && !!task?.completion_template_id)}
                                  options={templateOptions}/>
                        </Form.Item>
                        </div>
                      </Card>
                      {task && (
                        <div>
                          <div style={{marginBottom: 8}}><strong>Назначения:</strong></div>
                          <AssignmentTimeline assignments={assignmentTimeline.data} loading={assignmentTimeline.isLoading} error={assignmentTimeline.isError}/>
                        </div>
                      )}
                    </>
                  ),
                },
                {
                  key: 'dependencies',
                  label: `Зависимости (${depIds.size})`,
                  children: (
                    <Form.Item label="Зависит от">
                      <Input.Search placeholder="Поиск..." value={depSearch}
                                    onChange={(e) => setDepSearch(e.target.value)} style={{marginBottom: 8}} allowClear/>
                      <div style={{
                        maxHeight: 320,
                        overflowY: 'auto',
                        border: '1px solid rgba(128,128,128,0.3)',
                        borderRadius: 6,
                        padding: '4px 8px'
                      }}>
                        {filteredDeps.length === 0 && (
                          <span style={{color: 'rgba(128,128,128,0.8)'}}>
                            {depsLoading ? 'Загрузка...' : 'Нет совпадений'}
                          </span>
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
                  ),
                },
                ...(task ? [{
                  key: 'history',
                  label: 'История',
                  children: <HistoryPanel kind="task" entityId={task.id} open={activeTab === 'history'}/>,
                }] : []),
              ]}
            />
          )}
        </Form>
      </div>
    </Modal>
  );
}
