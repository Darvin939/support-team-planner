import {useState} from 'react';
import {Button, Card, Checkbox, Form, Input, message, Modal, Popconfirm, Space, Tag} from 'antd';
import {useMutation, useQueryClient} from '@tanstack/react-query';
import {type Team, useTeams} from '../../hooks/useTeams';
import {useBlockTemplates} from '../../hooks/useSettingsData';
import {apiMutate} from '../../lib/apiMutate';

interface TeamFormValues {
  name: string;
  template_ids: number[];
}

export function TeamsTab() {
  const { data: teams } = useTeams();
  const { data: templates } = useBlockTemplates();
  const queryClient = useQueryClient();
  const [modalTeam, setModalTeam] = useState<Team | 'new' | null>(null);
  const [form] = Form.useForm<TeamFormValues>();

  const saveMutation = useMutation({
    mutationFn: async (values: TeamFormValues) => {
      const isNew = modalTeam === 'new';
      const url = isNew ? '/api/teams' : `/api/teams/${(modalTeam as Team).id}`;
      return apiMutate(url, isNew ? 'POST' : 'PUT', values);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teams'] });
      message.success('Сохранено');
      setModalTeam(null);
    },
    onError: (e: Error) => message.error(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (teamId: number) => apiMutate(`/api/teams/${teamId}`, 'DELETE'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teams'] });
      message.success('Команда удалена');
    },
    onError: (e: Error) => message.error(e.message),
  });

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
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" onClick={() => openModal('new')}>
          Добавить команду
        </Button>
      </Space>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {teams?.map((team) => (
          <Card key={team.id} size="small">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <b>{team.name}</b>
              <Space>
                <Button size="small" onClick={() => openModal(team)}>
                  ✏️
                </Button>
                <Popconfirm
                  title="Удалить команду?"
                  description="Все связанные данные будут удалены!"
                  onConfirm={() => deleteMutation.mutate(team.id)}
                  okText="Удалить"
                  cancelText="Отмена"
                >
                  <Button size="small" danger>
                    🗑️
                  </Button>
                </Popconfirm>
              </Space>
            </div>
            {team.templates && team.templates.length > 0 && (
              <div style={{ marginTop: 8 }}>
                {team.templates.map((t) => (
                  <Tag key={t.id}>{t.name}</Tag>
                ))}
              </div>
            )}
          </Card>
        ))}
      </div>

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
