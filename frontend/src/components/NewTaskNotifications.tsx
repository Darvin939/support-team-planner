import {useEffect, useMemo, useState} from 'react';
import {useNavigate} from 'react-router-dom';
import {Alert, Button, Card, Drawer, Empty, List, Space, Spin, Typography} from 'antd';
import dayjs from 'dayjs';
import {CriticalityBadge} from './planningBadges';
import {PagePagination} from './PagePagination';
import {
  type NewTaskNotification,
  type NotificationCursor,
  useMarkNewTasksSeen,
  useNewTaskNotificationsPage,
  useNewTaskNotificationsPreview,
} from '../hooks/useNewTaskNotifications';
import {NotificationTabPanel, useDeferredDrawerNavigation, useNotificationCenter} from './NotificationCenter';

const PAGE_SIZE = 20;
export const NEW_TASK_POPOVER_LIMIT = 5;
const SESSION_KEY = 'new-task-overview-shown';

function TaskButton({item, onOpen}: {item: NewTaskNotification; onOpen: (item: NewTaskNotification) => void}) {
  return (
    <button type="button" onClick={() => onOpen(item)} style={{border: 0, background: 'none', padding: 0,
      textAlign: 'left', cursor: 'pointer', width: '100%'}} aria-label={`Открыть работу ${item.task_name}`}>
      <Space size={6}><CriticalityBadge value={item.criticality}/><Typography.Text strong>{item.task_name}</Typography.Text></Space>
      <Typography.Text type="secondary" style={{display: 'block', fontSize: 12}}>
        {item.author_name || 'Автор не указан'} · {dayjs(item.changed_at).format('DD.MM.YYYY HH:mm')}
      </Typography.Text>
    </button>
  );
}

export function GroupedNewTasks({items, onOpen}: {items: NewTaskNotification[]; onOpen: (item: NewTaskNotification) => void}) {
  const groups = useMemo(() => {
    const result = new Map<string, NewTaskNotification[]>();
    items.forEach((item) => result.set(item.team_name, [...(result.get(item.team_name) ?? []), item]));
    return [...result.entries()];
  }, [items]);
  return <>{groups.map(([team, teamItems]) => <div key={team} style={{marginBottom: 12}}>
    <Typography.Text strong>{team} ({teamItems.length})</Typography.Text>
    <List size="small" dataSource={teamItems} renderItem={(item) =>
      <List.Item><TaskButton item={item} onOpen={onOpen}/></List.Item>}/>
  </div>)}</>;
}

export function NewTasksDrawer({open, watermark, onClose, onOpenTask, afterOpenChange}: {
  open: boolean; watermark?: NotificationCursor; onClose: () => void;
  onOpenTask: (item: NewTaskNotification) => void; afterOpenChange?: (open: boolean) => void;
}) {
  const [page, setPage] = useState(1);
  useEffect(() => { if (open) setPage(1); }, [open, watermark]);
  const {data, isLoading, isError} = useNewTaskNotificationsPage((page - 1) * PAGE_SIZE, PAGE_SIZE, watermark);
  return <Drawer title={`Все новые работы${data ? ` (${data.total})` : ''}`} open={open} onClose={onClose}
    afterOpenChange={afterOpenChange} size={520}>
    {isLoading ? <div style={{textAlign: 'center'}}><Spin/></div> : isError ?
      <Alert type="error" showIcon title="Не удалось загрузить новые работы"/> : !data?.items.length ?
        <Empty description="Новых работ нет"/> : <>
          <GroupedNewTasks items={data.items} onOpen={onOpenTask}/>
          <PagePagination current={page} pageSize={PAGE_SIZE} total={data.total} onChange={setPage}/>
        </>}
  </Drawer>;
}

export function NewTasksOverviewCard() {
  const navigate = useNavigate();
  const {data, isLoading} = useNewTaskNotificationsPreview();
  const [visible, setVisible] = useState(() => sessionStorage.getItem(SESSION_KEY) !== '1');
  const [drawerOpen, setDrawerOpen] = useState(false);
  useEffect(() => {
    if (!isLoading && visible) sessionStorage.setItem(SESSION_KEY, '1');
  }, [isLoading, visible]);
  const openTask = (item: NewTaskNotification) => navigate(`/planning/${item.team_id}`, {state: {jumpTaskId: item.task_id}});
  const deferredNavigation = useDeferredDrawerNavigation(() => setDrawerOpen(false), openTask);
  if (!visible || !data?.total) return null;
  return <>
    <Card title={`Новые работы (${data.total})`} extra={<Button type="text" onClick={() => setVisible(false)} aria-label="Закрыть обзор">Закрыть</Button>}
          style={{marginBottom: 16}}>
      <GroupedNewTasks items={data.items.slice(0, 6)} onOpen={openTask}/>
      <Button onClick={() => setDrawerOpen(true)}>Показать все</Button>
    </Card>
    <NewTasksDrawer open={drawerOpen} watermark={data.watermark} onClose={() => setDrawerOpen(false)}
      onOpenTask={deferredNavigation.selectFromDrawer} afterOpenChange={deferredNavigation.afterOpenChange}/>
  </>;
}

export function NewTasksPanel() {
  const navigate = useNavigate();
  const {closeCenter} = useNotificationCenter();
  const {data, isLoading, isError} = useNewTaskNotificationsPreview();
  const markSeen = useMarkNewTasksSeen();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const openTask = (item: NewTaskNotification) => {
    closeCenter();
    navigate(`/planning/${item.team_id}`, {state: {jumpTaskId: item.task_id}});
  };
  const deferredNavigation = useDeferredDrawerNavigation(() => setDrawerOpen(false), openTask);
  const previewItems = data?.items.slice(0, NEW_TASK_POPOVER_LIMIT) ?? [];
  return <>
    <NotificationTabPanel shown={previewItems.length} total={data?.total ?? 0} loading={isLoading} error={isError}
      emptyText="Новых работ нет" actions={data?.total ? [
        {label: 'Показать все', onClick: () => setDrawerOpen(true)},
        {label: 'Отметить все просмотренными', primary: true, loading: markSeen.isPending,
          onClick: () => markSeen.mutate(data.watermark)},
      ] : []}>
      <GroupedNewTasks items={previewItems} onOpen={openTask}/>
    </NotificationTabPanel>
    <NewTasksDrawer open={drawerOpen} watermark={data?.watermark} onClose={() => setDrawerOpen(false)}
      onOpenTask={deferredNavigation.selectFromDrawer} afterOpenChange={deferredNavigation.afterOpenChange}/>
  </>;
}
