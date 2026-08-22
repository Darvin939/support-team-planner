import {useEffect, useState} from 'react';
import {Button, DatePicker, Input, Modal, Popconfirm, Space, Table, theme, Typography} from 'antd';
import dayjs, {type Dayjs} from 'dayjs';
import {AppPagination} from '../../components/AppPagination';
import {TASK_STATUS_LABELS, type TaskStatus} from '../../domain/types';
import {useDebouncedValue} from '../../hooks/useDebouncedValue';
import {type Task, useTaskArchive} from '../../hooks/usePlanningData';
import {API_DATE_FORMAT, DISPLAY_DATE_FORMAT} from '../../lib/dateFormats';
import {tintedStyle} from '../../components/planningBadges';
import {usePaginationState} from '../../hooks/usePaginationState';
import {useRestoreTaskMutation} from '../../hooks/useTaskMutations';

const PAGE_SIZE = 20;

export function TaskArchiveModal({open, teamId, canRestore, onClose}: {
  open: boolean;
  teamId: number;
  canRestore: boolean;
  onClose: () => void;
}) {
  const {token} = theme.useToken();
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search, 400);
  const [range, setRange] = useState<[Dayjs | null, Dayjs | null]>([null, null]);
  const pagination = usePaginationState(PAGE_SIZE);
  const from = range[0]?.format(API_DATE_FORMAT) ?? '';
  const to = range[1]?.format(API_DATE_FORMAT) ?? '';
  const archive = useTaskArchive(teamId, pagination.offset, pagination.pageSize, debouncedSearch, from, to, open);
  const restoreMutation = useRestoreTaskMutation();

  useEffect(() => pagination.reset(), [teamId, debouncedSearch, from, to, pagination.reset]);

  return (
    <Modal open={open} onCancel={onClose} footer={null} width={1000} title="Архив работ" destroyOnHidden>
      <Space wrap style={{marginBottom: 16}}>
        <DatePicker.RangePicker value={range} onChange={(value) => setRange(value ?? [null, null])}
                                format={DISPLAY_DATE_FORMAT} allowClear/>
        <Input.Search value={search} onChange={(event) => setSearch(event.target.value)}
                      allowClear placeholder="Поиск по названию и описанию" style={{width: 300}}/>
      </Space>
      <Table<Task>
        rowKey="id"
        size="small"
        loading={archive.isPending}
        dataSource={archive.data?.tasks ?? []}
        pagination={false}
        locale={{emptyText: 'В архиве нет подходящих работ'}}
        columns={[
          {title: 'Работа', dataIndex: 'name', key: 'name'},
          {title: 'Сегмент', dataIndex: 'segment_name', key: 'segment'},
          {title: 'Статус', dataIndex: 'task_status', key: 'status', render: (status: string) =>
            <span data-archive-task-status={status}
                  style={tintedStyle(status === 'done' ? token.colorSuccess : token.colorError)}>
              {TASK_STATUS_LABELS[status as TaskStatus] ?? status}
            </span>},
          {title: 'Дата завершения', dataIndex: 'completed_at', key: 'completed_at',
            render: (value: string | null) => value ? dayjs(value).format('DD.MM.YYYY HH:mm') :
              <Typography.Text type="secondary">Неизвестна</Typography.Text>},
          ...(canRestore ? [{
            title: 'Действия', key: 'actions', width: 130,
            render: (_: unknown, task: Task) => (
              <Popconfirm
                title="Восстановить работу?"
                description="Работа вернётся в активный список со статусом «Новый»."
                okText="Восстановить"
                cancelText="Отмена"
                onConfirm={() => restoreMutation.mutate(task.id)}
              >
                <Button type="link" loading={restoreMutation.isPending && restoreMutation.variables === task.id}>
                  Восстановить
                </Button>
              </Popconfirm>
            ),
          }] : []),
        ]}
      />
      <AppPagination current={pagination.page} pageSize={pagination.pageSize} total={archive.data?.total}
                     onChange={pagination.onChange}/>
    </Modal>
  );
}
