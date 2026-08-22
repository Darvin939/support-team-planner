import {useEffect, useState} from 'react';
import {Alert, Drawer, Empty, List, Spin, theme, Typography} from 'antd';
import {useNavigate} from 'react-router-dom';
import dayjs from 'dayjs';
import {type OverdueAssignment, useOverdueAssignments, useOverdueAssignmentsPage} from '../hooks/usePlanningData';
import {MAX_PERIOD_DAYS} from '../hooks/useDateRangeFilter';
import {DISPLAY_DATE_FORMAT} from '../lib/dateFormats';
import {CriticalityBadge} from './planningBadges';
import {AppPagination} from './AppPagination';
import {usePaginationState} from '../hooks/usePaginationState';
import {NotificationTabPanel, useDeferredDrawerNavigation, useNotificationCenter} from './NotificationCenter';

const OVERDUE_PAGE_SIZE = 20;

export function OverdueList({items, onOpen}: {items: OverdueAssignment[]; onOpen: (item: OverdueAssignment) => void}) {
  const {token} = theme.useToken();
  return <List size="small" dataSource={items} renderItem={(item) =>
    <List.Item onClick={() => onOpen(item)} style={{cursor: 'pointer', display: 'block', padding: '8px 4px'}}>
      <div style={{display: 'flex', alignItems: 'center', gap: 6}}>
        <CriticalityBadge value={item.criticality}/><span style={{fontWeight: 500}}>{item.task_name}</span>
      </div>
      <div style={{marginTop: 2, fontSize: '0.8rem', color: token.colorTextSecondary}}>
        {item.team_name} · {item.user_name || '—'} · {dayjs(item.date).format(DISPLAY_DATE_FORMAT)}
      </div>
    </List.Item>}/>;
}

export function OverdueDrawer({open, onClose, onOpen, afterOpenChange}: {
  open: boolean; onClose: () => void; onOpen: (item: OverdueAssignment) => void;
  afterOpenChange?: (open: boolean) => void;
}) {
  const pagination = usePaginationState(OVERDUE_PAGE_SIZE);
  useEffect(() => { if (open) pagination.reset(); }, [open, pagination.reset]);
  const {data, isLoading, isError} = useOverdueAssignmentsPage(
    pagination.offset, pagination.pageSize, open,
  );
  return <Drawer title={`Все просроченные назначения${data ? ` (${data.total})` : ''}`}
    open={open} onClose={onClose} afterOpenChange={afterOpenChange} size={520}>
    {isLoading ? <div style={{textAlign: 'center'}}><Spin/></div> : isError ?
      <Alert type="error" showIcon title="Не удалось загрузить просроченные назначения"/> : <>
        {!data?.items.length ? <Empty description="Просроченных назначений нет"/> :
          <OverdueList items={data.items} onOpen={onOpen}/>}
        <AppPagination compact current={pagination.page} pageSize={pagination.pageSize}
                       total={data?.total} onChange={pagination.onChange}/>
      </>}
  </Drawer>;
}

export function OverdueAssignmentsPanel() {
  const navigate = useNavigate();
  const {closeCenter} = useNotificationCenter();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const {data, isLoading, isError} = useOverdueAssignments();
  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  const navigateToAssignment = (item: OverdueAssignment) => {
    closeCenter();
    navigate(`/planning/${item.team_id}`, {state: {jumpTaskId: item.task_id, jumpDate: item.date}});
  };
  const deferredNavigation = useDeferredDrawerNavigation(() => setDrawerOpen(false), navigateToAssignment);

  return <>
    <Typography.Text strong>Просроченные назначения ({total}) за последние {MAX_PERIOD_DAYS} дней</Typography.Text>
    <NotificationTabPanel shown={items.length} total={total} loading={isLoading} error={isError}
      emptyText="Просроченных назначений нет"
      actions={total > 0 ? [{label: 'Показать все', onClick: () => setDrawerOpen(true)}] : []}>
      <OverdueList items={items} onOpen={navigateToAssignment}/>
    </NotificationTabPanel>
    <OverdueDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)}
      onOpen={deferredNavigation.selectFromDrawer} afterOpenChange={deferredNavigation.afterOpenChange}/>
  </>;
}
