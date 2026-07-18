import type {CSSProperties} from 'react';
import {Empty, Spin, theme} from 'antd';
import {useQuery} from '@tanstack/react-query';
import {useUserNames} from '../../hooks/useUserNames';
import {apiGet, buildApiUrl} from '../../lib/apiMutate';
import {formatChangedBy, formatHistoryText, type HistoryEntry} from '../../lib/historyFormat';
import {queryKeys} from '../../lib/queryKeys';

export const HISTORY_PAGE_SIZE = 10;
export type HistoryKind = 'task' | 'assignment';

export function useEntityHistory(kind: HistoryKind, entityId: number | null, offset: number, enabled = true) {
  return useQuery<{history: HistoryEntry[]; total: number}>({
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

  if (loading) return <Spin />;
  if (entries && entries.length === 0) {
    return <Empty description="Изменений пока нет" image={emptySimple ? Empty.PRESENTED_IMAGE_SIMPLE : undefined} />;
  }
  if (!entries) return null;

  return (
    <div style={{display: 'flex', flexDirection: 'column', gap: 6}}>
      {entries.map((entry) => (
        <div key={`${entry.entity ?? 'entity'}-${entry.id}`} style={itemStyle}>
          <div style={{opacity: 0.6, fontSize: compact ? '0.72rem' : '0.78rem'}}>
            {entry.changed_at} — {formatChangedBy(entry)}
          </div>
          <div>{formatHistoryText(entry, getUserName, showAssignmentContext)}</div>
        </div>
      ))}
    </div>
  );
}
