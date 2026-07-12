import {useState} from 'react';
import {DeleteOutlined, EditOutlined, LockOutlined} from '@ant-design/icons';
import {Button, Form, Input, List, Modal, Popconfirm, Select, Space, Switch, Tag, Tooltip} from 'antd';
import {type User, useUsers} from '../../hooks/useSettingsData';
import {useMe} from '../../hooks/useMe';
import {useCrudMutations} from '../../hooks/useCrudMutations';

interface UserFormValues {
  last_name: string | null;
  first_name: string;
  middle_name: string | null;
  login: string | null;
  password: string | null;
  role: string;
  is_assignee: boolean;
}

const ROLE_OPTIONS = [
  { value: 'user', label: 'Пользователь' },
  { value: 'editor', label: 'Редактор' },
  { value: 'admin', label: 'Администратор' },
];

export function UsersTab() {
  const { data: users } = useUsers();
  const { data: me } = useMe();
  const isAdmin = me?.role === 'admin';
  const [modalUser, setModalUser] = useState<User | 'new' | null>(null);
  const [form] = Form.useForm<UserFormValues>();

  const { saveMutation, deleteMutation } = useCrudMutations<User, UserFormValues>({
    queryKey: ['users'],
    baseUrl: '/api/users',
    modalEntity: modalUser,
    onSaveSuccess: () => setModalUser(null),
    deleteSuccessMessage: 'Пользователь удалён',
  });

  const isEditingProtected = modalUser !== 'new' && modalUser !== null && modalUser.is_protected;

  function openModal(u: User | 'new') {
    setModalUser(u);
    if (u === 'new') {
      form.setFieldsValue({ last_name: '', first_name: '', middle_name: '', login: '', password: '', role: 'user', is_assignee: true });
    } else {
      form.setFieldsValue({ last_name: u.last_name ?? '', first_name: u.first_name, middle_name: u.middle_name ?? '', login: u.login ?? '', password: '', role: u.role, is_assignee: u.is_assignee });
    }
  }

  return (
    <>
      {isAdmin && (
        <Space style={{ marginBottom: 16 }}>
          <Button type="primary" onClick={() => openModal('new')}>
            Добавить пользователя
          </Button>
        </Space>
      )}

      <List
        bordered
        dataSource={users}
        renderItem={(u) => (
          <List.Item
            actions={
              isAdmin
                ? [
                    <Button key="edit" size="small" onClick={() => openModal(u)}>
                      <EditOutlined />
                    </Button>,
                    u.is_protected ? (
                      <Tooltip key="delete" title="Учётную запись администратора по умолчанию нельзя удалить">
                        <Button size="small" danger disabled>
                          <DeleteOutlined />
                        </Button>
                      </Tooltip>
                    ) : (
                      <Popconfirm key="delete" title="Удалить пользователя?" onConfirm={() => deleteMutation.mutate(u.id)} okText="Удалить" cancelText="Отмена">
                        <Button size="small" danger>
                          <DeleteOutlined />
                        </Button>
                      </Popconfirm>
                    ),
                  ]
                : []
            }
          >
            {[u.last_name, u.first_name, u.middle_name].filter(Boolean).join(' ')} <Tag style={{ marginLeft: 8 }}>{u.role}</Tag>
            {u.login && <Tag style={{ marginLeft: 4 }}>{u.login}</Tag>}
            {!u.is_assignee && <Tag style={{ marginLeft: 4 }}>Не исполнитель</Tag>}
            {u.is_protected && (
              <Tooltip title="Учётную запись администратора по умолчанию нельзя удалить">
                <Tag icon={<LockOutlined />} color="default" style={{ marginLeft: 4 }}>
                  По умолчанию
                </Tag>
              </Tooltip>
            )}
          </List.Item>
        )}
      />

      <Modal
        title={modalUser === 'new' ? 'Добавить пользователя' : 'Редактирование пользователя'}
        open={modalUser !== null}
        onCancel={() => setModalUser(null)}
        onOk={() => form.submit()}
        okText={modalUser === 'new' ? 'Создать' : 'Обновить'}
        confirmLoading={saveMutation.isPending}
      >
        <Form form={form} layout="vertical" onFinish={(v) => saveMutation.mutate({ ...v, password: v.password || null })}>
          {isEditingProtected && (
            <Tag icon={<LockOutlined />} color="default" style={{ marginBottom: 16 }}>
              Для администратора по умолчанию можно изменить только логин и пароль
            </Tag>
          )}
          {!isEditingProtected && (
            <>
              <Form.Item name="first_name" label="Имя" rules={[{ required: true, message: 'Введите имя' }]}>
                <Input placeholder="Имя" />
              </Form.Item>
              <Form.Item name="last_name" label="Фамилия">
                <Input placeholder="Фамилия" />
              </Form.Item>
              <Form.Item name="middle_name" label="Отчество">
                <Input placeholder="Отчество" />
              </Form.Item>
              <Form.Item name="is_assignee" label="Может быть исполнителем" valuePropName="checked">
                <Switch />
              </Form.Item>
            </>
          )}
          <Form.Item name="login" label="Логин (оставьте пустым, чтобы не менять)">
            <Input placeholder="Логин для входа" />
          </Form.Item>
          <Form.Item name="password" label="Пароль (оставьте пустым, чтобы не менять)">
            <Input.Password placeholder="Новый пароль" />
          </Form.Item>
          {!isEditingProtected && (
            <Form.Item name="role" label="Роль">
              <Select options={ROLE_OPTIONS} />
            </Form.Item>
          )}
        </Form>
      </Modal>
    </>
  );
}
