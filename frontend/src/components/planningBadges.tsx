import {type CSSProperties, useState} from 'react';
import {CheckOutlined, CloseOutlined} from '@ant-design/icons';
import {Button, Popover, Space, theme, Tooltip} from 'antd';
import {ASSIGNMENT_STATUS_LABELS, TASK_STATUS_LABELS} from '../lib/historyFormat';

function tintedStyle(color: string): CSSProperties {
  return {
    display: 'inline-block',
    padding: '2px 8px',
    borderRadius: 12,
    fontWeight: 700,
    fontSize: '0.75rem',
    color,
    background: `color-mix(in srgb, ${color} 12%, transparent)`,
    border: `1px solid color-mix(in srgb, ${color} 35%, transparent)`,
  };
}

const CRIT_SHORT_LABEL: Record<string, string> = { high: 'В', medium: 'С', low: 'Н' };

export function CriticalityBadge({ value }: { value: string }) {
  const { token } = theme.useToken();
  const color = value === 'high' ? token.colorError : value === 'medium' ? token.colorWarning : token.colorSuccess;
  return <span style={tintedStyle(color)}>{CRIT_SHORT_LABEL[value] ?? value}</span>;
}

export function TaskStatusBadge({ value }: { value: string }) {
  const { token } = theme.useToken();
  if (value === 'new') return null;
  const color = value === 'done' ? token.colorSuccess : token.colorError;
  const icon = value === 'done' ? <CheckOutlined /> : <CloseOutlined />;
  return (
    <Tooltip title={TASK_STATUS_LABELS[value] ?? value}>
      <span style={{ color, fontSize: '0.95rem', display: 'inline-flex', alignItems: 'center' }}>{icon}</span>
    </Tooltip>
  );
}

export interface DepBadgeEntry {
  id: number;
  name: string;
  status: string;
  criticality: string;
  segmentName: string;
  isDeleted: boolean;
}

export function DepBadge({
  kind,
  deps,
  onNavigate,
}: {
  kind: 'deleted' | 'cancelled' | 'pending' | 'done';
  deps: DepBadgeEntry[];
  onNavigate: (dep: DepBadgeEntry) => void;
}) {
  const { token } = theme.useToken();
  const [open, setOpen] = useState(false);
  const color =
    kind === 'deleted' ? token.colorTextTertiary : kind === 'cancelled' ? token.colorError : kind === 'done' ? token.colorSuccess : token.colorWarning;
  const icon = kind === 'deleted' ? '🗑' : kind === 'cancelled' ? '⛔' : kind === 'done' ? '✔' : '⏳';
  const label = kind === 'deleted' ? 'зависимость удалена' : kind === 'cancelled' ? 'зависимость отменена' : kind === 'done' ? 'выполнено' : 'ожидает';

  const content = (
    <div style={{ width: 280, maxHeight: 320, overflow: 'auto' }}>
      <Space direction="vertical" size={10} style={{ width: '100%' }}>
        {deps.map((dep, i) => (
          <div key={dep.id} style={i > 0 ? { borderTop: `1px solid ${token.colorBorderSecondary}`, paddingTop: 10 } : undefined}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 500, overflowWrap: 'anywhere' }}>
              <CriticalityBadge value={dep.criticality} />
              <TaskStatusBadge value={dep.status} />
              {dep.name}
            </div>
            <div style={{ marginTop: 2, fontSize: '0.78rem', color: token.colorTextTertiary }}>{dep.segmentName}</div>
            <div style={{ marginTop: 6 }}>
              {dep.isDeleted ? (
                <span style={{ fontSize: '0.8rem', color: token.colorTextTertiary }}>Задача удалена</span>
              ) : (
                <Button size="small" type="link" style={{ padding: 0, height: 'auto' }} onClick={() => { setOpen(false); onNavigate(dep); }}>
                  Перейти к задаче
                </Button>
              )}
            </div>
          </div>
        ))}
      </Space>
    </div>
  );

  return (
    <Popover content={content} open={open} onOpenChange={setOpen} trigger="click" placement="bottomLeft">
      <span style={{ ...tintedStyle(color), borderRadius: 10, marginLeft: 4, cursor: 'pointer' }}>
        {icon} {label}: {deps.length}
      </span>
    </Popover>
  );
}

export function BlockRail({ block}: { block: string | null }) {
  const names = (block ?? '').split(',').map((s) => s.trim()).filter(Boolean);
  if (names.length === 0) return null;
  return (
    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
      <span style={{ fontWeight: 700, fontSize: '0.85rem' }}>{names.join(', ')}</span>
    </span>
  );
}

export interface AssignmentLite {
  id: number;
  block: string | null;
  status: 'new' | 'planned' | 'rollback' | 'success';
  user_name: string | null;
  comment: string | null;
  time_spent: string | null;
}

export function ScheduleChip({ assignment, onClick, draggable }: { assignment: AssignmentLite; onClick?: () => void; draggable?: boolean }) {
  const { token } = theme.useToken();
  const statusColor =
    assignment.status === 'planned' ? token.colorWarning : assignment.status === 'rollback' ? token.colorError : assignment.status === 'success' ? token.colorSuccess : token.colorPrimary;

  return (
    <div
      onClick={onClick}
      data-assignment-id={draggable ? assignment.id : undefined}
      style={{
        padding: '4px 7px 4px 9px',
        borderRadius: token.borderRadiusSM,
        minHeight: 32,
        display: 'flex',
        flexDirection: 'column',
        gap: 1,
        background: token.colorBgContainer,
        border: `1px solid ${token.colorBorder}`,
        borderLeft: `3px solid ${statusColor}`,
        cursor: onClick ? 'pointer' : undefined,
        textAlign: 'left',
      }}
    >
      <BlockRail block={assignment.block} />
      <span style={{ fontSize: '0.68rem', color: statusColor }}>{ASSIGNMENT_STATUS_LABELS[assignment.status] ?? assignment.status}</span>
      {assignment.comment && <span style={{ fontSize: '0.63rem', fontStyle: 'italic', color: token.colorTextTertiary }}>{assignment.comment}</span>}
      <span style={{ fontSize: '0.68rem', color: token.colorTextSecondary }}>{assignment.user_name}</span>
      {assignment.time_spent && (
        <span style={{ fontSize: '0.6rem', fontWeight: 700, letterSpacing: '0.03em', ...tintedStyle(token.colorPrimary), padding: '0 4px', borderRadius: 6 }}>
          {assignment.time_spent}
        </span>
      )}
    </div>
  );
}
