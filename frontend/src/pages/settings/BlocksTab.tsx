import {useState} from 'react';
import {DeleteOutlined, EditOutlined} from '@ant-design/icons';
import {Button, Card, Form, Input, InputNumber, List, message, Modal, Popconfirm, Select, Space, Tag} from 'antd';
import {useMutation, useQueryClient} from '@tanstack/react-query';
import {type BlockTemplate, useBlocks, useBlockTemplates, useSegments} from '../../hooks/useSettingsData';
import {useCrudMutations} from '../../hooks/useCrudMutations';
import {apiMutate} from '../../lib/apiMutate';

interface TemplateEntryValue {
  block_id: number;
  shift_days: number;
}

interface TemplateFormValues {
  name: string;
  segment_id: number;
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
                  <DeleteOutlined />
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
  const { data: segments } = useSegments();
  const [modalTemplate, setModalTemplate] = useState<BlockTemplate | 'new' | null>(null);
  const [form] = Form.useForm<TemplateFormValues>();

  const { saveMutation, deleteMutation } = useCrudMutations<BlockTemplate, TemplateFormValues>({
    queryKey: ['block-templates'],
    baseUrl: '/api/block-templates',
    modalEntity: modalTemplate,
    onSaveSuccess: () => setModalTemplate(null),
  });

  function openModal(tmpl: BlockTemplate | 'new') {
    setModalTemplate(tmpl);
    if (tmpl === 'new') {
      form.setFieldsValue({ name: '', segment_id: segments?.[0]?.id, entries: [{ block_id: blocks?.[0]?.id ?? 0, shift_days: 0 }] });
    } else {
      form.setFieldsValue({
        name: tmpl.name,
        segment_id: tmpl.segment_id,
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
              <Space>
                <b>{tmpl.name}</b>
                <Tag>{segments?.find((s) => s.id === tmpl.segment_id)?.name ?? '—'}</Tag>
              </Space>
              <Space>
                <Button size="small" onClick={() => openModal(tmpl)}>
                  <EditOutlined />
                </Button>
                <Popconfirm title="Удалить шаблон?" onConfirm={() => deleteMutation.mutate(tmpl.id)} okText="Удалить" cancelText="Отмена">
                  <Button size="small" danger>
                    <DeleteOutlined />
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

          <Form.Item name="segment_id" label="Сегмент" rules={[{ required: true, message: 'Выберите сегмент' }]}>
            <Select placeholder="Выберите сегмент" options={segments?.map((s) => ({ value: s.id, label: s.name }))} />
          </Form.Item>

          <Form.Item label="Блоки шаблона">
            <Form.List name="entries">
              {(fields, { add, remove }) => (
                <>
                  {fields.map((field) => (
                    <Space key={field.key} style={{ display: 'flex', marginBottom: 8 }} align="baseline">
                      <Form.Item name={[field.name, 'block_id']} noStyle rules={[{ required: true, message: 'Выберите блок' }]}>
                        <Select style={{ width: 180 }} showSearch={{ optionFilterProp: 'label' }} options={blocks?.map((b) => ({ value: b.id, label: b.name }))} />
                      </Form.Item>
                      <Form.Item name={[field.name, 'shift_days']} noStyle>
                        <InputNumber placeholder="Сдвиг, дни" />
                      </Form.Item>
                      <Button danger size="small" onClick={() => remove(field.name)}>
                        <DeleteOutlined />
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
