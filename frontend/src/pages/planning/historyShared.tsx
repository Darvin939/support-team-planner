import type {CSSProperties} from 'react';
import {Empty, Spin, Tag, theme} from 'antd';
import {useQuery} from '@tanstack/react-query';
import {useUserNames} from '../../hooks/useUserNames';
import {apiGet, buildApiUrl} from '../../lib/apiMutate';
import {formatChangedBy, formatHistoryValue, groupHistoryEntries, HISTORY_FIELD_LABELS, type HistoryEntry, type HistoryEvent} from '../../lib/historyFormat';
import {formatRussianCount} from '../../lib/format';
import {queryKeys} from '../../lib/queryKeys';

export const HISTORY_PAGE_SIZE = 10;
export type HistoryKind = 'task' | 'assignment';

export function useEntityHistory(kind: HistoryKind, entityId: number | null, offset: number, enabled = true) {
  return useQuery<{ history: HistoryEntry[]; total: number }>({
    queryKey: queryKeys.entityHistory(kind, entityId, offset),
    enabled: enabled && entityId !== null,
    queryFn: () => apiGet(buildApiUrl(`/api/${kind}/${entityId}/history`, {offset, limit: HISTORY_PAGE_SIZE})),
  });
}

export function HistoryEntries({
                                 entries,
                                 loading,
                                 showAssignmentContext,
                                 compact = false,
                                 emptySimple = false,
                               }: {
  entries: HistoryEntry[] | undefined;
  loading: boolean;
  showAssignmentContext: boolean;
  compact?: boolean;
  emptySimple?: boolean;
}) {
  const {token} = theme.useToken();
  const getUserName = useUserNames();
  const itemStyle: CSSProperties = {
    fontSize: compact ? '0.8rem' : '0.85rem',
    padding: '6px 10px',
    background: token.colorFillTertiary,
    borderRadius: token.borderRadiusSM,
  };
  const events = entries ? groupHistoryEntries(entries) : [];

  if (loading) return <Spin/>;
  if (entries && entries.length === 0) {
    return <Empty description="Изменений пока нет" image={emptySimple ? Empty.PRESENTED_IMAGE_SIMPLE : undefined}/>;
  }
  if (!entries) return null;

  return (
    <div style={{display: 'flex', flexDirection: 'column', gap: 6}}>
      {events.map((event) => {
        const first = event.entries[0];
        const eventKind = getHistoryEventKind(event);
        const objectKind = first.entity === 'assignment' || !showAssignmentContext ? 'назначение' : 'работа';
        const eventLabel = eventKind === 'created'
          ? `Создан${objectKind === 'работа' ? 'а' : 'о'} ${objectKind}`
          : eventKind === 'deleted'
            ? `Удален${objectKind === 'работа' ? 'а' : 'о'} ${objectKind}`
            : eventKind === 'restored'
              ? `Восстановлен${objectKind === 'работа' ? 'а' : 'о'} ${objectKind}`
              : 'Изменено';
        return <div key={event.key} style={itemStyle}>
          <Tag color={getHistoryEventColor(eventKind)} style={{margin: '0 0 2px'}}>{eventLabel}</Tag>
          <div style={{opacity: 0.6, fontSize: compact ? '0.72rem' : '0.78rem'}}>
            {first.changed_at} — {formatChangedBy(first)}
          </div>
          <HistoryChangeGrid event={event} getUserName={getUserName} showAssignmentContext={showAssignmentContext}/>
        </div>;
      })}
    </div>
  );
}

export function HistoryChangeGrid({event, getUserName, showAssignmentContext = true}: {
  event: HistoryEvent;
  getUserName: (id: string) => string;
  showAssignmentContext?: boolean;
}) {
  const {token} = theme.useToken();
  const cellStyle: CSSProperties = {padding: '4px 6px', overflowWrap: 'anywhere'};
  const headerStyle: CSSProperties = {...cellStyle, color: token.colorTextSecondary, fontSize: '0.75rem', fontWeight: 600};
  const firstEntry = event.entries[0];
  const createEvent = firstEntry.action === 'create';
  const deletedEntry = event.entries.find((entry) => entry.action === 'delete'
    || (entry.field_name === 'is_deleted' && entry.new_value === '1'));
  const deleteEvent = Boolean(deletedEntry);
  const showObjectColumn = showAssignmentContext;
  const labels = deleteEvent
    ? [...(showObjectColumn ? ['Объект'] : []), 'Событие']
    : createEvent
      ? [...(showObjectColumn ? ['Объект'] : []), 'Поле', 'Стало']
      : [...(showObjectColumn ? ['Объект'] : []), 'Поле', 'Было', 'Стало'];
  const columns = deleteEvent
    ? (showObjectColumn ? 'minmax(180px, 1fr) minmax(180px, 2fr)' : 'minmax(220px, 1fr)')
    : createEvent
      ? (showObjectColumn ? 'minmax(130px, 1fr) minmax(120px, 1fr) minmax(140px, 2fr)' : 'minmax(140px, 1fr) minmax(180px, 2fr)')
      : (showObjectColumn ? 'minmax(130px, 1fr) minmax(120px, 1fr) minmax(100px, 1fr) minmax(100px, 1fr)' : 'minmax(140px, 1fr) minmax(120px, 1fr) minmax(120px, 1fr)');
  const minWidth = deleteEvent ? (showObjectColumn ? 360 : 220) : createEvent ? (showObjectColumn ? 440 : 320) : (showObjectColumn ? 460 : 380);
  const displayedEntries = event.entries.flatMap((entry) => {
    if (entry.action !== 'create' || entry.field_name || !entry.new_value) return [entry];
    try {
      const snapshot = JSON.parse(entry.new_value) as Record<string, unknown>;
      const ignoredFields = new Set(['team_id', 'task_id']);
      const fields = Object.entries(snapshot).filter(([field]) => !ignoredFields.has(field));
      if (!fields.length) return [entry];
      return fields.map(([field_name, value]) => ({
        ...entry,
        id: entry.id * 100 + fields.findIndex(([name]) => name === field_name),
        action: 'create',
        field_name,
        old_value: null,
        new_value: value == null ? null : String(value),
      }));
    } catch {
      return [entry];
    }
  }).filter((entry) => !(entry.old_value == null || entry.old_value === '')
    || !(entry.new_value == null || entry.new_value === ''));
  if (!displayedEntries.length) return null;
  return <div style={{overflowX: 'auto', marginTop: 4}}>
    <div style={{minWidth}}>
      <div style={{display: 'grid', gridTemplateColumns: columns, borderBottom: `1px solid ${token.colorBorderSecondary}`}}>
        {labels.map((label) => <div key={label} style={headerStyle}>{label}</div>)}
      </div>
      {displayedEntries.map((entry) => {
        const assignment = entry.entity === 'assignment' || !showAssignmentContext;
        const object = assignment
          ? `Назначение${showAssignmentContext && entry.date ? ` · ${entry.date}` : ''}`
          : 'Работа';
        const isLifecycle = (entry.action === 'create' && !entry.field_name) || entry.action === 'delete' || entry.field_name === 'is_deleted';
        const field = isLifecycle ? 'Событие' : HISTORY_FIELD_LABELS[entry.field_name] || entry.field_name;
        const oldValue = isLifecycle ? '—' : formatHistoryValue(entry.field_name, entry.old_value, getUserName);
        const newValue = isLifecycle
          ? (entry.action === 'create' ? 'Создано' : entry.new_value === '1' || entry.action === 'delete' ? 'Удалено' : 'Восстановлено')
          : formatHistoryValue(entry.field_name, entry.new_value, getUserName);
        const values = deleteEvent
          ? [...(showObjectColumn ? [object] : []), deletedEntry?.action === 'delete' || deletedEntry?.new_value === '1' ? 'Удалено' : 'Восстановлено']
          : createEvent
            ? [...(showObjectColumn ? [object] : []), field, newValue]
            : [...(showObjectColumn ? [object] : []), field, oldValue, newValue];
        return <div key={`${entry.entity ?? 'entity'}-${entry.id}`} style={{display: 'grid', gridTemplateColumns: columns}}>
          {values.map((value, index) => <div key={index} style={cellStyle}>{value}</div>)}
        </div>;
      })}
    </div>
  </div>;
}

export function getHistoryEventKind(event: HistoryEvent): 'created' | 'deleted' | 'restored' | 'changed' {
  if (event.entries.some((entry) => entry.action === 'create')) return 'created';
  if (event.entries.some((entry) => entry.action === 'delete'
    || (entry.field_name === 'is_deleted' && entry.new_value === '1'))) return 'deleted';
  if (event.entries.some((entry) => entry.field_name === 'is_deleted' && entry.new_value === '0')) return 'restored';
  return 'changed';
}

export function getHistoryEventColor(kind: ReturnType<typeof getHistoryEventKind>): string | undefined {
  if (kind === 'created') return 'green';
  if (kind === 'deleted') return 'red';
  if (kind === 'restored') return 'blue';
  return undefined;
}

export function getHistoryEventSummary(event: HistoryEvent): string {
  const entry = event.entries[0];
  const kind: string = getHistoryEventKind(event);
  const isCreate = kind === 'created';
  const isDelete = kind === 'deleted';
  let fieldCount = event.entries.filter((item) => item.field_name && item.field_name !== 'is_deleted'
    && ((item.old_value != null && item.old_value !== '') || (item.new_value != null && item.new_value !== ''))).length;
  if (kind === 'created' && !fieldCount && entry.new_value) {
    try {
      const snapshot = JSON.parse(entry.new_value) as Record<string, unknown>;
      fieldCount = Object.entries(snapshot).filter(([field, value]) => field !== 'team_id' && field !== 'task_id'
        && value != null && value !== '').length;
    } catch {
      fieldCount = 0;
    }
  }
  if (isCreate) return fieldCount ? `Создано · ${formatRussianCount(fieldCount, {one: 'поле', few: 'поля', many: 'полей'})}` : 'Создано';
  if (isDelete) return 'Удалено';
  if (kind === 'restored') return 'Восстановлено';
  return fieldCount ? `Изменено · ${formatRussianCount(fieldCount, {one: 'поле', few: 'поля', many: 'полей'})}` : 'Изменение';
}
