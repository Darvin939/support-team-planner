import {useState} from 'react';
import {DeleteOutlined, EditOutlined} from '@ant-design/icons';
import {Button, Card, Form, Input, List, Modal, Popconfirm, Space} from 'antd';
import {type Segment, useSegments} from '../../hooks/useSettingsData';
import {useCrudMutations} from '../../hooks/useCrudMutations';

interface SegmentFormValues {
  name: string;
}

export function SegmentsTab() {
  const { data: segments } = useSegments();
  const [modalSegment, setModalSegment] = useState<Segment | 'new' | null>(null);
  const [form] = Form.useForm<SegmentFormValues>();

  const { saveMutation, deleteMutation } = useCrudMutations<Segment, SegmentFormValues>({
    queryKey: ['segments'],
    baseUrl: '/api/segments',
    modalEntity: modalSegment,
    onSaveSuccess: () => setModalSegment(null),
    deleteSuccessMessage: 'Сегмент удалён',
  });

  function openModal(segment: Segment | 'new') {
    setModalSegment(segment);
    form.setFieldsValue({ name: segment === 'new' ? '' : segment.name });
  }

  return (
    <Card title="Сегменты работ">
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" onClick={() => openModal('new')}>
          Добавить сегмент
        </Button>
      </Space>

      <List
        bordered
        dataSource={segments}
        renderItem={(segment) => (
          <List.Item
            actions={[
              <Button key="edit" size="small" onClick={() => openModal(segment)}>
                <EditOutlined />
              </Button>,
              <Popconfirm
                key="delete"
                title="Удалить сегмент?"
                description="Удаление невозможно, пока сегмент используется в работах или шаблонах блоков."
                onConfirm={() => deleteMutation.mutate(segment.id)}
                okText="Удалить"
                cancelText="Отмена"
              >
                <Button size="small" danger>
                  <DeleteOutlined />
                </Button>
              </Popconfirm>,
            ]}
          >
            {segment.name}
          </List.Item>
        )}
      />

      <Modal
        title={modalSegment === 'new' ? 'Добавить сегмент' : 'Редактирование сегмента'}
        open={modalSegment !== null}
        onCancel={() => setModalSegment(null)}
        onOk={() => form.submit()}
        okText={modalSegment === 'new' ? 'Создать' : 'Обновить'}
        confirmLoading={saveMutation.isPending}
      >
        <Form form={form} layout="vertical" onFinish={(v) => saveMutation.mutate(v)}>
          <Form.Item name="name" label="Название сегмента" rules={[{ required: true, message: 'Введите название сегмента' }]}>
            <Input placeholder="Название сегмента" />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
