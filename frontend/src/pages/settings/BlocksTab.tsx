import {useState} from 'react';
import {Button, Card, Form, Input, InputNumber, List, message, Modal, Popconfirm, Select, Space} from 'antd';
import {useMutation, useQueryClient} from '@tanstack/react-query';
import {type BlockTemplate, useBlocks, useBlockTemplates} from '../../hooks/useSettingsData';
import {apiMutate} from '../../lib/apiMutate';

interface TemplateEntryValue {
  block_id: number;
  shift_days: number;
}

interface TemplateFormValues {
  name: string;
  entries: TemplateEntryValue[];
}

function BlocksList() {
  const { data: blocks } = useBlocks();
  const queryClient = useQueryClient();
  const [newBlockName, setNewBlockName] = useState('');

  const createMutation = useMutation({
    mutationFn: (name: string) => apiMutate('/api/blocks', 'POST', { name }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['blocks'] });
      setNewBlockName('');
    },
    onError: (e: Error) => message.error(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (blockId: number) => apiMutate(`/api/blocks/${blockId}`, 'DELETE'),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['blocks'] }),
    onError: (e: Error) => message.error(e.message),
  });

  return (
    <Card title="Блоки раскатки" style={{ marginBottom: 16 }}>
      <Space.Compact style={{ width: '100%', marginBottom: 16 }}>
        <Input
          placeholder="Название блока (например: ГФ, Б1)"
          value={newBlockName}
          onChange={(e) => setNewBlockName(e.target.value)}
          onPressEnter={() => newBlockName.trim() && createMutation.mutate(newBlockName.trim())}
        />
        <Button type="primary" onClick={() => newBlockName.trim() && createMutation.mutate(newBlockName.trim())}>
          Добавить
        </Button>
      </Space.Compact>
      <List
        bordered
        dataSource={blocks}
        renderItem={(block) => (
          <List.Item
            actions={[
              <Popconfirm key="delete" title="Удалить блок?" description="Он будет удалён из всех шаблонов." onConfirm={() => deleteMutation.mutate(block.id)} okText="Удалить" cancelText="Отмена">
                <Button size="small" danger>
                  🗑️
                </Button>
              </Popconfirm>,
            ]}
          >
            {block.name}
          </List.Item>
        )}
      />
    </Card>
  );
}

function TemplatesList() {
  const { data: templates } = useBlockTemplates();
  const { data: blocks } = useBlocks();
  const queryClient = useQueryClient();
  const [modalTemplate, setModalTemplate] = useState<BlockTemplate | 'new' | null>(null);
  const [form] = Form.useForm<TemplateFormValues>();

  const saveMutation = useMutation({
    mutationFn: async (values: TemplateFormValues) => {
      const isNew = modalTemplate === 'new';
      const url = isNew ? '/api/block-templates' : `/api/block-templates/${(modalTemplate as BlockTemplate).id}`;
      return apiMutate(url, isNew ? 'POST' : 'PUT', values);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['block-templates'] });
      message.success('Сохранено');
      setModalTemplate(null);
    },
    onError: (e: Error) => message.error(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (templateId: number) => apiMutate(`/api/block-templates/${templateId}`, 'DELETE'),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['block-templates'] }),
    onError: (e: Error) => message.error(e.message),
  });

  function openModal(tmpl: BlockTemplate | 'new') {
    setModalTemplate(tmpl);
    if (tmpl === 'new') {
      form.setFieldsValue({ name: '', entries: [{ block_id: blocks?.[0]?.id ?? 0, shift_days: 0 }] });
    } else {
      form.setFieldsValue({
        name: tmpl.name,
        entries: tmpl.blocks.length ? tmpl.blocks.map((b) => ({ block_id: b.id, shift_days: b.shift_days })) : [{ block_id: blocks?.[0]?.id ?? 0, shift_days: 0 }],
      });
    }
  }

  return (
    <Card title="Шаблоны блоков">
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" onClick={() => openModal('new')}>
          Добавить шаблон
        </Button>
      </Space>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {templates?.map((tmpl) => (
          <Card key={tmpl.id} size="small">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <b>{tmpl.name}</b>
              <Space>
                <Button size="small" onClick={() => openModal(tmpl)}>
                  ✏️
                </Button>
                <Popconfirm title="Удалить шаблон?" onConfirm={() => deleteMutation.mutate(tmpl.id)} okText="Удалить" cancelText="Отмена">
                  <Button size="small" danger>
                    🗑️
                  </Button>
                </Popconfirm>
              </Space>
            </div>
            {tmpl.blocks.length > 0 && (
              <table style={{ marginTop: 8, width: '100%' }}>
                <tbody>
                  {tmpl.blocks.map((b, i) => (
                    <tr key={i}>
                      <td>{b.name}</td>
                      <td>+{b.shift_days} дн.</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        ))}
      </div>

      <Modal
        title={modalTemplate === 'new' ? 'Добавить шаблон' : 'Редактирование шаблона'}
        open={modalTemplate !== null}
        onCancel={() => setModalTemplate(null)}
        onOk={() => form.submit()}
        okText={modalTemplate === 'new' ? 'Создать' : 'Обновить'}
        confirmLoading={saveMutation.isPending}
      >
        <Form form={form} layout="vertical" onFinish={(v) => saveMutation.mutate(v)}>
          <Form.Item name="name" label="Название шаблона" rules={[{ required: true, message: 'Введите название шаблона' }]}>
            <Input placeholder="Название шаблона" />
          </Form.Item>

          <Form.Item label="Блоки шаблона">
            <Form.List name="entries">
              {(fields, { add, remove }) => (
                <>
                  {fields.map((field) => (
                    <Space key={field.key} style={{ display: 'flex', marginBottom: 8 }} align="baseline">
                      <Form.Item name={[field.name, 'block_id']} noStyle rules={[{ required: true, message: 'Выберите блок' }]}>
                        <Select style={{ width: 180 }} options={blocks?.map((b) => ({ value: b.id, label: b.name }))} />
                      </Form.Item>
                      <Form.Item name={[field.name, 'shift_days']} noStyle>
                        <InputNumber placeholder="Сдвиг, дни" />
                      </Form.Item>
                      <Button danger size="small" onClick={() => remove(field.name)}>
                        🗑️
                      </Button>
                    </Space>
                  ))}
                  <Button type="dashed" onClick={() => add({ block_id: blocks?.[0]?.id ?? 0, shift_days: 0 })} block>
                    + Добавить блок
                  </Button>
                </>
              )}
            </Form.List>
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}

export function BlocksTab() {
  return (
    <>
      <BlocksList />
      <TemplatesList />
    </>
  );
}
