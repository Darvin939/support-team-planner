import type {CSSProperties} from 'react';
import {theme} from 'antd';
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
  const color =
    value === 'ready' ? token.colorPrimary : value === 'in_progress' ? token.colorWarning : value === 'done' ? token.colorSuccess : token.colorError;
  return <span style={{ ...tintedStyle(color), borderRadius: 10, fontWeight: 600 }}>{TASK_STATUS_LABELS[value] ?? value}</span>;
}

export function DepBadge({ kind, names }: { kind: 'deleted' | 'cancelled' | 'pending'; names: string[] }) {
  const { token } = theme.useToken();
  const color = kind === 'deleted' ? token.colorTextTertiary : kind === 'cancelled' ? token.colorError : token.colorWarning;
  const icon = kind === 'deleted' ? '🗑' : kind === 'cancelled' ? '⛔' : '⏳';
  const label = kind === 'deleted' ? 'зависимость удалена' : kind === 'cancelled' ? 'зависимость отменена' : 'ожидает';
  return (
    <span title={names.join(', ')} style={{ ...tintedStyle(color), borderRadius: 10, marginLeft: 4 }}>
      {icon} {label}: {names.length}
    </span>
  );
}

export function BlockRail({ block, dotColor }: { block: string | null; dotColor: string }) {
  const names = (block ?? '').split(',').map((s) => s.trim()).filter(Boolean);
  if (names.length === 0) return null;
  return (
    <span style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', rowGap: 2, lineHeight: 1.2 }}>
      {names.map((name, i) => (
        <span key={i} style={{ display: 'flex', alignItems: 'center' }}>
          {i > 0 && <span style={{ width: 9, height: 1, background: 'currentColor', opacity: 0.35, margin: '0 4px' }} />}
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: dotColor, flexShrink: 0 }} />
            <span style={{ fontWeight: 700, fontSize: '0.85rem' }}>{name}</span>
          </span>
        </span>
      ))}
    </span>
  );
}

export interface AssignmentLite {
  id: number;
  block: string | null;
  status: 'new' | 'planned' | 'rollback' | 'success';
  employee_name: string | null;
  comment: string | null;
  is_psi: boolean;
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
      <BlockRail block={assignment.block} dotColor={statusColor} />
      <span style={{ fontSize: '0.68rem', color: statusColor }}>{ASSIGNMENT_STATUS_LABELS[assignment.status] ?? assignment.status}</span>
      {assignment.comment && <span style={{ fontSize: '0.63rem', fontStyle: 'italic', color: token.colorTextTertiary }}>{assignment.comment}</span>}
      <span style={{ fontSize: '0.68rem', color: token.colorTextSecondary }}>{assignment.employee_name}</span>
      {(assignment.is_psi || assignment.time_spent) && (
        <span style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          {assignment.is_psi && (
            <span style={{ fontSize: '0.6rem', fontWeight: 700, letterSpacing: '0.03em', ...tintedStyle('#9254de'), padding: '0 4px', borderRadius: 6 }}>ПСИ</span>
          )}
          {assignment.time_spent && (
            <span style={{ fontSize: '0.6rem', fontWeight: 700, letterSpacing: '0.03em', ...tintedStyle(token.colorPrimary), padding: '0 4px', borderRadius: 6 }}>
              {assignment.time_spent}
            </span>
          )}
        </span>
      )}
    </div>
  );
}
