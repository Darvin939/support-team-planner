import {useState} from 'react';
import {Button, Form, Input, List, message, Modal, Popconfirm, Select, Space, Tag} from 'antd';
import {useMutation, useQueryClient} from '@tanstack/react-query';
import {type Employee, useEmployees} from '../../hooks/useSettingsData';
import {useMe} from '../../hooks/useMe';
import {apiMutate} from '../../lib/apiMutate';

interface EmployeeFormValues {
  last_name: string;
  first_name: string;
  middle_name: string | null;
  password: string | null;
  role: string;
}

const ROLE_OPTIONS = [
  { value: 'user', label: 'Пользователь' },
  { value: 'editor', label: 'Редактор' },
  { value: 'admin', label: 'Администратор' },
];

export function EmployeesTab() {
  const { data: employees } = useEmployees();
  const { data: me } = useMe();
  const isAdmin = me?.role === 'admin';
  const queryClient = useQueryClient();
  const [modalEmployee, setModalEmployee] = useState<Employee | 'new' | null>(null);
  const [form] = Form.useForm<EmployeeFormValues>();

  const saveMutation = useMutation({
    mutationFn: async (values: EmployeeFormValues) => {
      const isNew = modalEmployee === 'new';
      const url = isNew ? '/api/employees' : `/api/employees/${(modalEmployee as Employee).id}`;
      return apiMutate(url, isNew ? 'POST' : 'PUT', { ...values, password: values.password || null });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['employees'] });
      message.success('Сохранено');
      setModalEmployee(null);
    },
    onError: (e: Error) => message.error(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (employeeId: number) => apiMutate(`/api/employees/${employeeId}`, 'DELETE'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['employees'] });
      message.success('Сотрудник удалён');
    },
    onError: (e: Error) => message.error(e.message),
  });

  function openModal(emp: Employee | 'new') {
    setModalEmployee(emp);
    if (emp === 'new') {
      form.setFieldsValue({ last_name: '', first_name: '', middle_name: '', password: '', role: 'user' });
    } else {
      form.setFieldsValue({ last_name: emp.last_name, first_name: emp.first_name, middle_name: emp.middle_name ?? '', password: '', role: emp.role });
    }
  }

  return (
    <>
      {isAdmin && (
        <Space style={{ marginBottom: 16 }}>
          <Button type="primary" onClick={() => openModal('new')}>
            Добавить сотрудника
          </Button>
        </Space>
      )}

      <List
        bordered
        dataSource={employees}
        renderItem={(emp) => (
          <List.Item
            actions={
              isAdmin
                ? [
                    <Button key="edit" size="small" onClick={() => openModal(emp)}>
                      ✏️
                    </Button>,
                    <Popconfirm key="delete" title="Удалить сотрудника?" onConfirm={() => deleteMutation.mutate(emp.id)} okText="Удалить" cancelText="Отмена">
                      <Button size="small" danger>
                        🗑️
                      </Button>
                    </Popconfirm>,
                  ]
                : []
            }
          >
            {emp.last_name} {emp.first_name} {emp.middle_name ?? ''} <Tag style={{ marginLeft: 8 }}>{emp.role}</Tag>
          </List.Item>
        )}
      />

      <Modal
        title={modalEmployee === 'new' ? 'Добавить сотрудника' : 'Редактирование сотрудника'}
        open={modalEmployee !== null}
        onCancel={() => setModalEmployee(null)}
        onOk={() => form.submit()}
        okText={modalEmployee === 'new' ? 'Создать' : 'Обновить'}
        confirmLoading={saveMutation.isPending}
      >
        <Form form={form} layout="vertical" onFinish={(v) => saveMutation.mutate(v)}>
          <Form.Item name="last_name" label="Фамилия" rules={[{ required: true, message: 'Введите фамилию' }]}>
            <Input placeholder="Фамилия" />
          </Form.Item>
          <Form.Item name="first_name" label="Имя" rules={[{ required: true, message: 'Введите имя' }]}>
            <Input placeholder="Имя" />
          </Form.Item>
          <Form.Item name="middle_name" label="Отчество">
            <Input placeholder="Отчество" />
          </Form.Item>
          <Form.Item name="password" label="Пароль (оставьте пустым, чтобы не менять)">
            <Input.Password placeholder="Новый пароль" />
          </Form.Item>
          <Form.Item name="role" label="Роль">
            <Select options={ROLE_OPTIONS} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
