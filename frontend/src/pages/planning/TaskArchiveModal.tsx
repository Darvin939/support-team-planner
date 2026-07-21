import {useEffect, useState} from 'react';
import {Button, DatePicker, Input, message, Modal, Popconfirm, Space, Table, theme, Typography} from 'antd';
import {useMutation, useQueryClient} from '@tanstack/react-query';
import dayjs, {type Dayjs} from 'dayjs';
import {OffsetPagination} from '../../components/OffsetPagination';
import {TASK_STATUS_LABELS} from '../../domain/types';
import {useDebouncedValue} from '../../hooks/useDebouncedValue';
import {type Task, useTaskArchive} from '../../hooks/usePlanningData';
import {API_DATE_FORMAT, DISPLAY_DATE_FORMAT} from '../../lib/dateFormats';
import {apiMutate} from '../../lib/apiMutate';
import {queryKeys} from '../../lib/queryKeys';
import {tintedStyle} from '../../components/planningBadges';

const PAGE_SIZE = 20;

export function TaskArchiveModal({open, teamId, canRestore, onClose}: {
  open: boolean;
  teamId: number;
  canRestore: boolean;
  onClose: () => void;
}) {
  const {token} = theme.useToken();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search, 400);
  const [range, setRange] = useState<[Dayjs | null, Dayjs | null]>([null, null]);
  const [offset, setOffset] = useState(0);
  const from = range[0]?.format(API_DATE_FORMAT) ?? '';
  const to = range[1]?.format(API_DATE_FORMAT) ?? '';
  const archive = useTaskArchive(teamId, offset, PAGE_SIZE, debouncedSearch, from, to, open);
  const restoreMutation = useMutation({
    mutationFn: (taskId: number) => apiMutate(`/api/task/${taskId}/restore`, 'POST'),
    onSuccess: async () => {
      await queryClient.invalidateQueries({queryKey: queryKeys.tasks.all});
      message.success('Работа восстановлена');
    },
    onError: (error: Error) => message.error(error.message),
  });

  useEffect(() => setOffset(0), [teamId, debouncedSearch, from, to]);

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
              {TASK_STATUS_LABELS[status] ?? status}
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
      <OffsetPagination offset={offset} pageSize={PAGE_SIZE} total={archive.data?.total ?? 0}
                        onOffsetChange={setOffset} style={{marginTop: 16, textAlign: 'center'}}/>
    </Modal>
  );
}
