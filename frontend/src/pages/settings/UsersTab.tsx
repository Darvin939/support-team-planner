import {useEffect, useState} from 'react';
import type {TableColumnsType} from 'antd';
import {Button, Form, Input, Modal, Pagination, Popconfirm, Select, Space, Switch, Table, Tag, Tooltip} from 'antd';
import {DeleteOutlined, EditOutlined, LockOutlined} from '@ant-design/icons';
import {usePaginatedUsers, type User} from '../../hooks/useSettingsData';
import {useMe} from '../../hooks/useMe';
import {useCrudMutations} from '../../hooks/useCrudMutations';
import {DEFAULT_PAGE_SIZE, PAGE_SIZE_OPTIONS} from '../../lib/pagination';
import {useTeams} from '../../hooks/useTeams';
import {useDebouncedValue} from '../../hooks/useDebouncedValue';
import {usePaginationState} from '../../hooks/usePaginationState';
import {useIsMobile} from "../../hooks/useIsMobile";
import {TOP_BAR_HEIGHT} from "../../components/AppShell";
import {queryKeys} from '../../lib/queryKeys';

interface UserFormValues {
  last_name: string | null;
  first_name: string;
  middle_name: string | null;
  login: string | null;
  password: string | null;
  role: string;
  is_assignee: boolean;
  team_ids: number[];
}

const ROLE_OPTIONS = [
  {value: 'user', label: 'Пользователь'},
  {value: 'editor', label: 'Редактор'},
  {value: 'admin', label: 'Администратор'},
];

const VISIBLE_TEAM_LIMIT = 3;

export function UsersTab() {
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search.trim(), 350);
  const pagination = usePaginationState(DEFAULT_PAGE_SIZE);
  const {page, pageSize} = pagination;
  const {data, isLoading} = usePaginatedUsers(pagination.offset, pageSize, debouncedSearch);
  const {data: teams} = useTeams();
  const {data: me} = useMe();
  const isAdmin = me?.role === 'admin';
  const [modalUser, setModalUser] = useState<User | 'new' | null>(null);
  const [form] = Form.useForm<UserFormValues>();
  const isMobile = useIsMobile();

  const {saveMutation, deleteMutation} = useCrudMutations<User, UserFormValues>({
    queryKey: queryKeys.users.all,
    baseUrl: '/api/users',
    modalEntity: modalUser,
    onSaveSuccess: () => setModalUser(null),
    deleteSuccessMessage: 'Пользователь удалён',
  });

  const isEditingProtected = modalUser !== 'new' && modalUser !== null && modalUser.is_protected;

  useEffect(() => {
    if (data && data.users.length === 0 && data.total > 0 && page > 1) pagination.setPage(page - 1);
  }, [data, page, pagination]);

  const columns: TableColumnsType<User> = [
    {
      title: 'ФИО', key: 'fullName',
      render: (_, user) => <Space size={4} wrap>
        <span>{[user.last_name, user.first_name, user.middle_name].filter(Boolean).join(' ')}</span>
        {!user.is_assignee && <Tag>Не исполнитель</Tag>}
        {user.is_protected &&
            <Tooltip title="Учётную запись администратора по умолчанию нельзя удалить"><Tag icon={<LockOutlined/>}>По
                умолчанию</Tag></Tooltip>}
      </Space>,
    },
    {
      title: 'Роль',
      dataIndex: 'role',
      key: 'role',
      render: (role: string) => ROLE_OPTIONS.find((item) => item.value === role)?.label ?? role
    },
    {title: 'Логин', dataIndex: 'login', key: 'login', render: (login: string | null) => login || '—'},
    {
      title: 'Команды', key: 'teams', width: 360,
      render: (_, user) => {
        if (user.team_ids.length === 0) return <Tag color="blue">Все команды</Tag>;

        const selectedTeamIds = new Set(user.team_ids);
        const teamNames = (teams ?? [])
          .filter((team) => selectedTeamIds.has(team.id))
          .map((team) => team.name);
        if (teamNames.length === 0) return '—';

        const visibleTeamNames = teamNames.slice(0, VISIBLE_TEAM_LIMIT);
        const hiddenCount = teamNames.length - visibleTeamNames.length;
        return (
          <Space wrap>
            {visibleTeamNames.map((teamName) => <Tag key={teamName}>{teamName}</Tag>)}
            {hiddenCount > 0 && (
              <Tooltip title={teamNames.join(', ')}>
                <Tag>+{hiddenCount}</Tag>
              </Tooltip>
            )}
          </Space>
        );
      },
    },
    {
      title: 'Действия', key: 'actions', width: 120,
      render: (_, user) => isAdmin ? <Space>
        <Button aria-label="Редактировать пользователя" size="small"
                onClick={() => openModal(user)}><EditOutlined/></Button>
        {user.is_protected
          ? <Tooltip title="Учётную запись администратора по умолчанию нельзя удалить"><Button
            aria-label="Удалить пользователя" size="small" danger disabled><DeleteOutlined/></Button></Tooltip>
          : <Popconfirm title="Удалить пользователя?" onConfirm={() => deleteMutation.mutate(user.id)} okText="Удалить"
                        cancelText="Отмена"><Button aria-label="Удалить пользователя" size="small"
                                                    danger><DeleteOutlined/></Button></Popconfirm>}
      </Space> : null,
    },
  ];

  function openModal(u: User | 'new') {
    setModalUser(u);
    if (u === 'new') {
      form.setFieldsValue({
        last_name: '',
        first_name: '',
        middle_name: '',
        login: '',
        password: '',
        role: 'user',
        is_assignee: true,
        team_ids: []
      });
    } else {
      form.setFieldsValue({
        last_name: u.last_name ?? '',
        first_name: u.first_name,
        middle_name: u.middle_name ?? '',
        login: u.login ?? '',
        password: '',
        role: u.role,
        is_assignee: u.is_assignee,
        team_ids: u.team_ids ?? []
      });
    }
  }

  return (
    <>
      <Space wrap style={{marginBottom: 16, display: 'flex', width: '100%'}}>
        {isAdmin && (
          <Button type="primary" onClick={() => openModal('new')}>
            Добавить пользователя
          </Button>
        )}
        <Input.Search allowClear value={search} placeholder="Поиск по логину, ФИО или роли"
                      onChange={(event) => {
                        setSearch(event.target.value);
                        pagination.reset();
                      }} style={{width: 420, maxWidth: '100%'}}/>
      </Space>
      <Table<User> rowKey="id" columns={columns} dataSource={data?.users ?? []} loading={isLoading}
                   pagination={false} scroll={{x: 1080}} sticky={{offsetHeader: isMobile ? TOP_BAR_HEIGHT : 0}}/>
      {(data?.total ?? 0) > pageSize && <Pagination current={page} pageSize={pageSize} total={data?.total ?? 0}
                                                    showSizeChanger pageSizeOptions={PAGE_SIZE_OPTIONS}
                                                    style={{marginTop: 16, textAlign: 'right'}}
                                                    onChange={pagination.onChange}/>}

      <Modal
        title={modalUser === 'new' ? 'Добавить пользователя' : 'Редактирование пользователя'}
        open={modalUser !== null}
        onCancel={() => setModalUser(null)}
        onOk={() => form.submit()}
        okText={modalUser === 'new' ? 'Создать' : 'Обновить'}
        confirmLoading={saveMutation.isPending}
      >
        <Form form={form} layout="vertical" onFinish={(v) => saveMutation.mutate({...v, password: v.password || null})}>
          {isEditingProtected && (
            <Tag icon={<LockOutlined/>} color="default" style={{marginBottom: 16}}>
              Для администратора по умолчанию можно изменить только логин и пароль
            </Tag>
          )}
          {!isEditingProtected && (
            <>
              <Form.Item name="first_name" label="Имя" rules={[{required: true, message: 'Введите имя'}]}>
                <Input placeholder="Имя"/>
              </Form.Item>
              <Form.Item name="last_name" label="Фамилия">
                <Input placeholder="Фамилия"/>
              </Form.Item>
              <Form.Item name="middle_name" label="Отчество">
                <Input placeholder="Отчество"/>
              </Form.Item>
              <Form.Item name="is_assignee" label="Может быть исполнителем" valuePropName="checked">
                <Switch/>
              </Form.Item>
            </>
          )}
          <Form.Item name="login" label="Логин (оставьте пустым, чтобы не менять)">
            <Input placeholder="Логин для входа"/>
          </Form.Item>
          <Form.Item name="password" label="Пароль (оставьте пустым, чтобы не менять)">
            <Input.Password placeholder="Новый пароль"/>
          </Form.Item>
          {!isEditingProtected && (
            <Form.Item name="role" label="Роль">
              <Select options={ROLE_OPTIONS}/>
            </Form.Item>
          )}
          {!isEditingProtected && (
            <Form.Item noStyle shouldUpdate={(prev, next) => prev.role !== next.role}>
              {({getFieldValue}) => (
                <Form.Item name="team_ids" label="Доступные команды"
                           extra={getFieldValue('role') === 'admin' ? 'Администратору всегда доступны все команды' : 'Если команды не выбраны, доступны все команды'}>
                  <Select mode="multiple" allowClear disabled={getFieldValue('role') === 'admin'}
                          placeholder="Все команды"
                          options={teams?.map((team) => ({value: team.id, label: team.name}))}/>
                </Form.Item>
              )}
            </Form.Item>
          )}
        </Form>
      </Modal>
    </>
  );
}
