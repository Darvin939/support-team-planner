import {useEffect, useState} from 'react';
import type {TableColumnsType} from 'antd';
import {DeleteOutlined, EditOutlined} from '@ant-design/icons';
import {Button, Checkbox, Form, Input, Modal, Pagination, Popconfirm, Space, Table, Tag} from 'antd';
import {type Team, usePaginatedTeams} from '../../hooks/useTeams';
import {useBlockTemplates} from '../../hooks/useSettingsData';
import {useCrudMutations} from '../../hooks/useCrudMutations';
import {DEFAULT_PAGE_SIZE, PAGE_SIZE_OPTIONS} from '../../lib/pagination';
import {useDebouncedValue} from '../../hooks/useDebouncedValue';
import {usePaginationState} from '../../hooks/usePaginationState';

interface TeamFormValues {
  name: string;
  template_ids: number[];
}

export function TeamsTab() {
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search.trim(), 350);
  const pagination = usePaginationState(DEFAULT_PAGE_SIZE);
  const {page, pageSize} = pagination;
  const {data, isLoading} = usePaginatedTeams(pagination.offset, pageSize, debouncedSearch);
  const { data: templates } = useBlockTemplates();
  const [modalTeam, setModalTeam] = useState<Team | 'new' | null>(null);
  const [form] = Form.useForm<TeamFormValues>();

  const { saveMutation, deleteMutation } = useCrudMutations<Team, TeamFormValues>({
    queryKey: ['teams'],
    baseUrl: '/api/teams',
    modalEntity: modalTeam,
    onSaveSuccess: () => setModalTeam(null),
    deleteSuccessMessage: 'Команда удалена',
  });

  useEffect(() => {
    if (data && data.teams.length === 0 && data.total > 0 && page > 1) pagination.setPage(page - 1);
  }, [data, page, pagination]);

  const columns: TableColumnsType<Team> = [
    {title: 'Название', dataIndex: 'name', key: 'name'},
    {
      title: 'Шаблоны', key: 'templates',
      render: (_, team) => team.templates?.length
        ? <Space wrap>{team.templates.map((template) => <Tag key={template.id}>{template.name}</Tag>)}</Space>
        : '—',
    },
    {
      title: 'Действия', key: 'actions', width: 120,
      render: (_, team) => <Space>
        <Button aria-label="Редактировать команду" size="small" onClick={() => openModal(team)}>
          <EditOutlined />
        </Button>
        <Popconfirm
          title="Удалить команду?"
          description="Все связанные данные будут удалены!"
          onConfirm={() => deleteMutation.mutate(team.id)}
          okText="Удалить"
          cancelText="Отмена"
        >
          <Button aria-label="Удалить команду" size="small" danger>
            <DeleteOutlined />
          </Button>
        </Popconfirm>
      </Space>,
    },
  ];

  function openModal(team: Team | 'new') {
    setModalTeam(team);
    if (team === 'new') {
      form.setFieldsValue({ name: '', template_ids: [] });
    } else {
      form.setFieldsValue({ name: team.name, template_ids: team.templates?.map((t) => t.id) ?? [] });
    }
  }

  return (
    <>
      <Space wrap style={{ marginBottom: 16, display: 'flex', width: '100%' }}>
        <Button type="primary" onClick={() => openModal('new')}>
          Добавить команду
        </Button>
        <Input.Search allowClear value={search} placeholder="Поиск по названию команды"
          onChange={(event) => { setSearch(event.target.value); pagination.reset(); }} style={{width: 420, maxWidth: '100%'}} />
      </Space>

      <Table<Team> rowKey="id" columns={columns} dataSource={data?.teams ?? []} loading={isLoading}
        pagination={false} scroll={{x: 720}} />
      {(data?.total ?? 0) > pageSize && <Pagination current={page} pageSize={pageSize} total={data?.total ?? 0}
        showSizeChanger pageSizeOptions={PAGE_SIZE_OPTIONS} style={{marginTop: 16, textAlign: 'right'}}
        onChange={pagination.onChange} />}

      <Modal
        title={modalTeam === 'new' ? 'Добавить команду' : 'Редактирование команды'}
        open={modalTeam !== null}
        onCancel={() => setModalTeam(null)}
        onOk={() => form.submit()}
        okText={modalTeam === 'new' ? 'Создать' : 'Обновить'}
        confirmLoading={saveMutation.isPending}
      >
        <Form form={form} layout="vertical" onFinish={(v) => saveMutation.mutate(v)}>
          <Form.Item name="name" label="Название команды" rules={[{ required: true, message: 'Введите название команды' }]}>
            <Input placeholder="Название команды" />
          </Form.Item>
          <Form.Item name="template_ids" label="Разрешённые шаблоны блоков">
            <Checkbox.Group
              options={templates?.map((t) => ({ value: t.id, label: t.name }))}
              style={{ display: 'flex', flexDirection: 'column', gap: 4 }}
            />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
