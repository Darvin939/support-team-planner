import {Space} from 'antd';
import {StatGroupLabel, StatTile} from '../../components/StatTile';

export function PlanningStats({items}: {
  items: {status: string; criticality: string}[] | undefined;
}) {
  const status = {new: 0, planned: 0};
  const criticality = {high: 0, medium: 0, low: 0};
  for (const item of items ?? []) {
    if (item.status in status) status[item.status as keyof typeof status]++;
    if (item.criticality in criticality) criticality[item.criticality as keyof typeof criticality]++;
  }
  return (
    <Space size={8} wrap style={{marginBottom: 14}}>
      <StatTile label="На сегодня" value={items?.length ?? 0} primary/>
      <StatGroupLabel>Статус</StatGroupLabel>
      <StatTile label="Новый" value={status.new} accent="#1668dc"/>
      <StatTile label="Запланировано" value={status.planned} accent="#d89614"/>
      <StatGroupLabel>Критичность</StatGroupLabel>
      <StatTile label="Высокая" value={criticality.high} accent="#d32029"/>
      <StatTile label="Средняя" value={criticality.medium} accent="#d89614"/>
      <StatTile label="Низкая" value={criticality.low} accent="#49aa19"/>
    </Space>
  );
}
