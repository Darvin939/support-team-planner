import {ApartmentOutlined, InboxOutlined} from '@ant-design/icons';
import {Button, Popconfirm, Space} from 'antd';

export function PlanningToolbar(props: {
  selectedIds: Set<number>;
  bulkDeletePending: boolean;
  total: number;
  visible: number;
  borderColor: string;
  secondaryTextColor: string;
  onAdd: () => void;
  onGraph: () => void;
  onArchive: () => void;
  onDeleteSelected: () => void;
  onClearSelection: () => void;
}) {
  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      marginBottom: 12, flexWrap: 'wrap', gap: 8,
    }}>
      <Space wrap>
        <Button type="primary" onClick={props.onAdd}>Добавить работу</Button>
        <Button icon={<ApartmentOutlined/>} onClick={props.onGraph}>Граф зависимостей</Button>
        <Button icon={<InboxOutlined/>} onClick={props.onArchive}>Архив</Button>
        {props.selectedIds.size > 0 && (
          <Space size={8} style={{paddingLeft: 8, borderLeft: `1px solid ${props.borderColor}`}}>
            <span style={{color: props.secondaryTextColor}}>Выбрано: {props.selectedIds.size}</span>
            <Popconfirm
              title={`Удалить ${props.selectedIds.size} назначений?`}
              okText="Удалить"
              cancelText="Отмена"
              onConfirm={props.onDeleteSelected}
            >
              <Button danger loading={props.bulkDeletePending}>Удалить</Button>
            </Popconfirm>
            <Button onClick={props.onClearSelection}>Снять выделение</Button>
          </Space>
        )}
      </Space>
      <span style={{
        fontFamily: "'JetBrains Mono Variable', monospace",
        color: props.secondaryTextColor,
        fontSize: '0.9rem',
      }}>
        Всего работ: {props.total} | Отображено: {props.visible}
      </span>
    </div>
  );
}
