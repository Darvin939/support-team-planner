import {useState} from 'react';
import {useNavigate} from 'react-router-dom';
import {Badge, Empty, List, Popover, Spin, theme, Typography} from 'antd';
import dayjs from 'dayjs';
import {useOverdueAssignments} from '../hooks/usePlanningData';
import {MAX_PERIOD_DAYS} from '../hooks/useDateRangeFilter';
import {CriticalityBadge} from './planningBadges';
import {DISPLAY_DATE_FORMAT} from '../lib/dateFormats';

const iconStyle = { width: 17, height: 17, display: 'inline-flex' } as const;

function BellIcon() {
  return (
    <span style={iconStyle}>
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
        <path d="M10 3.2c-2 0-3.4 1.6-3.4 3.8v2.2c0 .9-.3 1.8-.9 2.5l-.7.9h10l-.7-.9a3.9 3.9 0 0 1-.9-2.5V7c0-2.2-1.4-3.8-3.4-3.8Z" />
        <path d="M8.3 15.3a1.8 1.8 0 0 0 3.4 0" />
      </svg>
    </span>
  );
}

export function OverdueNotifications({ compact }: { compact?: boolean }) {
  const { token } = theme.useToken();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const { data, isLoading, isError } = useOverdueAssignments();
  const items = data ?? [];

  function handleItemClick(item: NonNullable<typeof data>[number]) {
    setOpen(false);
    navigate(`/planning/${item.team_id}`, { state: { jumpTaskId: item.task_id, jumpDate: item.date } });
  }

  const content = (
    <div style={{ width: 320, maxHeight: 380, overflow: 'auto' }}>
      <Typography.Text strong>
        Просроченные назначения ({items.length}) за последние {MAX_PERIOD_DAYS} дней
      </Typography.Text>
      <div style={{ marginTop: 8 }}>
        {isLoading ? (
          <div style={{ textAlign: 'center', padding: '16px 0' }}>
            <Spin size="small" />
          </div>
        ) : isError ? (
          <Typography.Text type="danger">Не удалось загрузить</Typography.Text>
        ) : items.length === 0 ? (
          <Empty description="Просроченных назначений нет" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          <List
            size="small"
            dataSource={items}
            renderItem={(item) => (
              <List.Item
                onClick={() => handleItemClick(item)}
                style={{ cursor: 'pointer', display: 'block', padding: '8px 4px' }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <CriticalityBadge value={item.criticality} />
                  <span style={{ fontWeight: 500 }}>{item.task_name}</span>
                </div>
                <div style={{ marginTop: 2, fontSize: '0.8rem', color: token.colorTextSecondary }}>
                  {item.team_name} · {item.user_name || '—'} · {dayjs(item.date).format(DISPLAY_DATE_FORMAT)}
                </div>
              </List.Item>
            )}
          />
        )}
      </div>
    </div>
  );

  return (
    <Popover content={content} open={open} onOpenChange={setOpen} trigger="click" placement="bottomLeft">
      <button
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: compact ? 0 : 11,
          width: compact ? 'auto' : '100%',
          padding: compact ? 4 : '8px 10px',
          background: 'none',
          border: 'none',
          color: 'inherit',
          cursor: 'pointer',
          textAlign: 'left',
          fontSize: '0.88rem',
        }}
      >
        <Badge count={items.length} color={token.colorError} size="small">
          <BellIcon />
        </Badge>
        {!compact && <span>Уведомления</span>}
      </button>
    </Popover>
  );
}
