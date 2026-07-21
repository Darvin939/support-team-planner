import {useMemo, useState} from 'react';
import type {TableColumnsType} from 'antd';
import {
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  message,
  Modal,
  Pagination,
  Popconfirm,
  Row,
  Select,
  Space,
  Table,
  Tag
} from 'antd';
import {DeleteOutlined, EditOutlined} from '@ant-design/icons';
import {useMutation, useQueryClient} from '@tanstack/react-query';
import {
  type Block,
  type BlockTemplate,
  type Segment,
  useBlocks,
  useBlockTemplates,
  useSegments,
} from '../../hooks/useSettingsData';
import {useCrudMutations} from '../../hooks/useCrudMutations';
import {apiMutate} from '../../lib/apiMutate';


const DIRECTORY_PAGE_SIZE = 5;

interface TemplateEntryValue {
  block_id: number;
  shift_days: number;
}

interface TemplateFormValues {
  name: string;
  segment_id: number;
  entries: TemplateEntryValue[];
}

interface SegmentFormValues {
  name: string;
}

interface BlockFormValues {
  name: string;
}

function useClientDirectory<T>(items: T[] | undefined, getSearchText: (item: T) => string) {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const filteredItems = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase('ru-RU');
    if (!needle) return items ?? [];
    return (items ?? []).filter((item) => getSearchText(item).toLocaleLowerCase('ru-RU').includes(needle));
  }, [items, search, getSearchText]);
  const pageCount = Math.max(1, Math.ceil(filteredItems.length / DIRECTORY_PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const pageItems = filteredItems.slice(
    (currentPage - 1) * DIRECTORY_PAGE_SIZE,
    currentPage * DIRECTORY_PAGE_SIZE,
  );

  function updateSearch(value: string) {
    setSearch(value);
    setPage(1);
  }

  return {search, updateSearch, currentPage, setPage, filteredItems, pageItems};
}

function DirectoryPagination({total, page, onChange}: {
  total: number;
  page: number;
  onChange: (page: number) => void
}) {
  if (total <= DIRECTORY_PAGE_SIZE) return null;
  return (
    <Pagination size="small" current={page} pageSize={DIRECTORY_PAGE_SIZE} total={total}
                showSizeChanger={false} style={{marginTop: 12, textAlign: 'right'}} onChange={onChange}/>
  );
}

function DirectoryToolbar({buttonText, searchPlaceholder, search, onSearchChange, onAdd}: {
  buttonText: string;
  searchPlaceholder: string;
  search: string;
  onSearchChange: (value: string) => void;
  onAdd: () => void;
}) {
  return (
    <Space wrap style={{display: 'flex', width: '100%', marginBottom: 12}}>
      <Button type="primary" onClick={onAdd}>{buttonText}</Button>
      <Input.Search allowClear value={search} placeholder={searchPlaceholder}
                    onChange={(event) => onSearchChange(event.target.value)} style={{width: 260, maxWidth: '100%'}}/>
    </Space>
  );
}

function SegmentsPanel() {
  const {data: segments, isLoading} = useSegments();
  const directory = useClientDirectory(segments, (segment) => segment.name);
  const [modalSegment, setModalSegment] = useState<Segment | 'new' | null>(null);
  const [form] = Form.useForm<SegmentFormValues>();
  const {saveMutation, deleteMutation} = useCrudMutations<Segment, SegmentFormValues>({
    queryKey: ['segments'],
    baseUrl: '/api/segments',
    modalEntity: modalSegment,
    onSaveSuccess: () => setModalSegment(null),
    deleteSuccessMessage: 'Сегмент удалён',
  });

  function openModal(segment: Segment | 'new') {
    setModalSegment(segment);
    form.setFieldsValue({name: segment === 'new' ? '' : segment.name});
  }

  const columns: TableColumnsType<Segment> = [
    {title: 'Название', dataIndex: 'name', key: 'name'},
    {
      title: 'Действия', key: 'actions', width: 104,
      render: (_, segment) => <Space>
        <Button aria-label="Редактировать сегмент" size="small"
                onClick={() => openModal(segment)}><EditOutlined/></Button>
        <Popconfirm title="Удалить сегмент?"
                    description="Удаление невозможно, пока сегмент используется в работах или шаблонах блоков."
                    onConfirm={() => deleteMutation.mutate(segment.id)} okText="Удалить" cancelText="Отмена">
          <Button aria-label="Удалить сегмент" size="small" danger><DeleteOutlined/></Button>
        </Popconfirm>
      </Space>,
    },
  ];

  return (
    <Card title="Сегменты" size="small">
      <DirectoryToolbar buttonText="Добавить сегмент" searchPlaceholder="Поиск сегментов"
                        search={directory.search} onSearchChange={directory.updateSearch}
                        onAdd={() => openModal('new')}/>
      <Table<Segment> rowKey="id" size="small" columns={columns} dataSource={directory.pageItems}
                      loading={isLoading} pagination={false} scroll={{x: 360}}/>
      <DirectoryPagination total={directory.filteredItems.length} page={directory.currentPage}
                           onChange={directory.setPage}/>
      <Modal title={modalSegment === 'new' ? 'Добавить сегмент' : 'Редактирование сегмента'}
             open={modalSegment !== null} onCancel={() => setModalSegment(null)} onOk={() => form.submit()}
             okText={modalSegment === 'new' ? 'Создать' : 'Обновить'} confirmLoading={saveMutation.isPending}>
        <Form form={form} layout="vertical" onFinish={(values) => saveMutation.mutate(values)}>
          <Form.Item name="name" label="Название сегмента"
                     rules={[{required: true, message: 'Введите название сегмента'}]}>
            <Input placeholder="Название сегмента"/>
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}

function BlocksPanel() {
  const {data: blocks, isLoading} = useBlocks();
  const directory = useClientDirectory(blocks, (block) => block.name);
  const queryClient = useQueryClient();
  const [blockModalOpen, setBlockModalOpen] = useState(false);
  const [form] = Form.useForm<BlockFormValues>();
  const createMutation = useMutation({
    mutationFn: (name: string) => apiMutate('/api/blocks', 'POST', {name}),
    onSuccess: () => {
      queryClient.invalidateQueries({queryKey: ['blocks']});
      setBlockModalOpen(false);
      form.resetFields();
    },
    onError: (error: Error) => message.error(error.message),
  });
  const deleteMutation = useMutation({
    mutationFn: (blockId: number) => apiMutate(`/api/blocks/${blockId}`, 'DELETE'),
    onSuccess: () => queryClient.invalidateQueries({queryKey: ['blocks']}),
    onError: (error: Error) => message.error(error.message),
  });

  const columns: TableColumnsType<Block> = [
    {title: 'Название', dataIndex: 'name', key: 'name'},
    {
      title: 'Действия', key: 'actions', width: 84,
      render: (_, block) => <Popconfirm title="Удалить блок?" description="Он будет удалён из всех шаблонов."
                                        onConfirm={() => deleteMutation.mutate(block.id)} okText="Удалить"
                                        cancelText="Отмена">
        <Button aria-label="Удалить блок" size="small" danger><DeleteOutlined/></Button>
      </Popconfirm>,
    },
  ];

  return (
    <Card title="Блоки" size="small">
      <DirectoryToolbar buttonText="Добавить блок" searchPlaceholder="Поиск блоков"
                        search={directory.search} onSearchChange={directory.updateSearch}
                        onAdd={() => {
                          form.resetFields();
                          setBlockModalOpen(true);
                        }}/>
      <Table<Block> rowKey="id" size="small" columns={columns} dataSource={directory.pageItems}
                    loading={isLoading} pagination={false} scroll={{x: 320}}/>
      <DirectoryPagination total={directory.filteredItems.length} page={directory.currentPage}
                           onChange={directory.setPage}/>
      <Modal title="Добавить блок" open={blockModalOpen} onCancel={() => setBlockModalOpen(false)}
             onOk={() => form.submit()} okText="Создать" confirmLoading={createMutation.isPending}>
        <Form form={form} layout="vertical"
              onFinish={(values) => createMutation.mutate(values.name.trim())}>
          <Form.Item name="name" label="Название блока" rules={[{required: true, message: 'Введите название блока'}]}>
            <Input placeholder="Название блока (например: GF, Б1)"/>
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}

function formatTemplateBlock(name: string, shiftDays: number) {
  return `${name} ${shiftDays >= 0 ? '+' : ''}${shiftDays} дн.`;
}

function TemplatesPanel() {
  const {data: templates, isLoading} = useBlockTemplates();
  const {data: blocks} = useBlocks();
  const {data: segments} = useSegments();
  const segmentNames = useMemo(
    () => new Map((segments ?? []).map((segment) => [segment.id, segment.name])),
    [segments],
  );
  const directory = useClientDirectory(templates, (template) => [
    template.name,
    segmentNames.get(template.segment_id) ?? '',
    ...template.blocks.map((block) => block.name),
  ].join(' '));
  const [modalTemplate, setModalTemplate] = useState<BlockTemplate | 'new' | null>(null);
  const [form] = Form.useForm<TemplateFormValues>();
  const {saveMutation, deleteMutation} = useCrudMutations<BlockTemplate, TemplateFormValues>({
    queryKey: ['block-templates'],
    baseUrl: '/api/block-templates',
    modalEntity: modalTemplate,
    onSaveSuccess: () => setModalTemplate(null),
  });

  function openModal(template: BlockTemplate | 'new') {
    setModalTemplate(template);
    if (template === 'new') {
      form.setFieldsValue({
        name: '',
        segment_id: segments?.[0]?.id,
        entries: [{block_id: blocks?.[0]?.id ?? 0, shift_days: 0}]
      });
    } else {
      form.setFieldsValue({
        name: template.name,
        segment_id: template.segment_id,
        entries: template.blocks.length
          ? template.blocks.map((block) => ({block_id: block.id, shift_days: block.shift_days}))
          : [{block_id: blocks?.[0]?.id ?? 0, shift_days: 0}],
      });
    }
  }

  const columns: TableColumnsType<BlockTemplate> = [
    {title: 'Название', dataIndex: 'name', key: 'name', width: 160},
    {
      title: 'Сегмент', key: 'segment', width: 130,
      render: (_, template) => <Tag>{segmentNames.get(template.segment_id) ?? '—'}</Tag>,
    },
    {
      title: 'Состав', key: 'blocks',
      render: (_, template) => {
        if (template.blocks.length === 0) return '—';
        const labels = template.blocks.map((block) => formatTemplateBlock(block.name, block.shift_days));
        return <Space wrap>
          {labels.map((label) => <Tag key={label}>{label}</Tag>)}
        </Space>;
      },
    },
    {
      title: 'Действия', key: 'actions', width: 104,
      render: (_, template) => <Space>
        <Button aria-label="Редактировать шаблон" size="small"
                onClick={() => openModal(template)}><EditOutlined/></Button>
        <Popconfirm title="Удалить шаблон?" onConfirm={() => deleteMutation.mutate(template.id)}
                    okText="Удалить" cancelText="Отмена">
          <Button aria-label="Удалить шаблон" size="small" danger><DeleteOutlined/></Button>
        </Popconfirm>
      </Space>,
    },
  ];

  return (
    <Card title="Шаблоны блоков" size="small">
      <DirectoryToolbar buttonText="Добавить шаблон" searchPlaceholder="Поиск шаблонов"
                        search={directory.search} onSearchChange={directory.updateSearch}
                        onAdd={() => openModal('new')}/>
      <Table<BlockTemplate> rowKey="id" size="small" columns={columns} dataSource={directory.pageItems}
                            loading={isLoading} pagination={false} scroll={{x: 720}}/>
      <DirectoryPagination total={directory.filteredItems.length} page={directory.currentPage}
                           onChange={directory.setPage}/>
      <Modal title={modalTemplate === 'new' ? 'Добавить шаблон' : 'Редактирование шаблона'}
             open={modalTemplate !== null} onCancel={() => setModalTemplate(null)} onOk={() => form.submit()}
             okText={modalTemplate === 'new' ? 'Создать' : 'Обновить'} confirmLoading={saveMutation.isPending}>
        <Form form={form} layout="vertical" onFinish={(values) => saveMutation.mutate(values)}>
          <Form.Item name="name" label="Название шаблона"
                     rules={[{required: true, message: 'Введите название шаблона'}]}>
            <Input placeholder="Название шаблона"/>
          </Form.Item>
          <Form.Item name="segment_id" label="Сегмент" rules={[{required: true, message: 'Выберите сегмент'}]}>
            <Select placeholder="Выберите сегмент"
                    options={segments?.map((segment) => ({value: segment.id, label: segment.name}))}/>
          </Form.Item>
          <Form.Item label="Блоки шаблона">
            <Form.List name="entries">
              {(fields, {add, remove}) => <>
                {fields.map((field) => <Space key={field.key} style={{display: 'flex', marginBottom: 8}}
                                              align="baseline">
                  <Form.Item name={[field.name, 'block_id']} noStyle
                             rules={[{required: true, message: 'Выберите блок'}]}>
                    <Select style={{width: 180}} showSearch={{optionFilterProp: 'label'}}
                            options={blocks?.map((block) => ({value: block.id, label: block.name}))}/>
                  </Form.Item>
                  <Form.Item name={[field.name, 'shift_days']} noStyle>
                    <InputNumber placeholder="Сдвиг, дни"/>
                  </Form.Item>
                  <Button aria-label="Удалить блок из шаблона" danger size="small" onClick={() => remove(field.name)}>
                    <DeleteOutlined/>
                  </Button>
                </Space>)}
                <Button type="dashed" onClick={() => add({block_id: blocks?.[0]?.id ?? 0, shift_days: 0})} block>
                  + Добавить блок
                </Button>
              </>}
            </Form.List>
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}

export function WorkReferencesTab() {
  return (
    <Row gutter={[16, 16]} align="top">
      <Col xs={24} xl={9}>
        <Space orientation="vertical" size={16} style={{display: 'flex', width: '100%'}}>
          <SegmentsPanel/>
          <BlocksPanel/>
        </Space>
      </Col>
      <Col xs={24} xl={15}>
        <TemplatesPanel/>
      </Col>
    </Row>
  );
}
