import {useState} from 'react';
import {Badge, Popover, Tabs, theme} from 'antd';
import {useOverdueAssignments} from '../hooks/usePlanningData';
import {NewTasksPanel} from './NewTaskNotifications';
import {useNewTaskNotificationsPreview} from '../hooks/useNewTaskNotifications';
import {NotificationCenterProvider} from './NotificationCenter';
import {OverdueAssignmentsPanel} from './OverdueAssignmentsPanel';

const iconStyle = {width: 17, height: 17, display: 'inline-flex'} as const;

function BellIcon() {
  return <span style={iconStyle}><svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}
    strokeLinecap="round" strokeLinejoin="round">
    <path d="M10 3.2c-2 0-3.4 1.6-3.4 3.8v2.2c0 .9-.3 1.8-.9 2.5l-.7.9h10l-.7-.9a3.9 3.9 0 0 1-.9-2.5V7c0-2.2-1.4-3.8-3.4-3.8Z"/>
    <path d="M8.3 15.3a1.8 1.8 0 0 0 3.4 0"/>
  </svg></span>;
}

export function OverdueNotifications({compact}: {compact?: boolean}) {
  const {token} = theme.useToken();
  const [open, setOpen] = useState(false);
  const {data} = useOverdueAssignments();
  const {data: newTasksData} = useNewTaskNotificationsPreview();
  const total = data?.total ?? 0;

  const content = <NotificationCenterProvider value={{closeCenter: () => setOpen(false)}}>
    <div style={{width: 400, maxWidth: 'calc(100vw - 32px)'}}>
      <Tabs size="small" destroyOnHidden style={{width: '100%'}} items={[
        {key: 'new-tasks', label: `Новые работы (${newTasksData?.total ?? 0})`, children: <NewTasksPanel/>},
        {key: 'overdue', label: `Просроченные (${total})`, children: <OverdueAssignmentsPanel/>},
      ]}/>
    </div>
  </NotificationCenterProvider>;

  return <Popover content={content} open={open} onOpenChange={setOpen} trigger="click" placement="bottomLeft">
    <button aria-label="Уведомления" style={{display: 'flex', alignItems: 'center', gap: compact ? 0 : 11, width: compact ? 'auto' : '100%',
      padding: compact ? 4 : '8px 10px', background: 'none', border: 'none', color: 'inherit', cursor: 'pointer',
      textAlign: 'left', fontSize: '0.88rem'}}>
      <Badge count={total + (newTasksData?.total ?? 0)} overflowCount={99} color={token.colorError} size="small">
        <BellIcon/>
      </Badge>
      {!compact && <span>Уведомления</span>}
    </button>
  </Popover>;
}
