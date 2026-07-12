import {useEffect, useState} from 'react';
import {Button, Empty, Pagination, Spin, theme} from 'antd';
import {useQuery} from '@tanstack/react-query';
import {formatChangedBy, formatHistoryText, type HistoryEntry} from '../../lib/historyFormat';
import {useUserNames} from '../../hooks/useUserNames';
import {useIsMobile} from '../../hooks/useIsMobile';
import {apiGet} from '../../lib/apiMutate';

const HISTORY_PAGE_SIZE = 10;

/** Resets (and optionally auto-opens) the panel every time the owning modal transitions to open — mirrors the original's resetHistoryPanel-on-every-openModal-call behavior. */
export function useHistoryToggle(modalOpen: boolean, autoOpen: boolean) {
  const [open, setOpen] = useState(autoOpen);
  useEffect(() => {
    if (modalOpen) setOpen(autoOpen);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modalOpen]);
  return [open, setOpen] as const;
}

export function HistoryToggleButton({ open, onClick }: { open: boolean; onClick: () => void }) {
  return <Button onClick={onClick}>{open ? '✕ Скрыть историю' : '🕓 История'}</Button>;
}

export function HistoryPanel({ kind, entityId, open }: { kind: 'task' | 'assignment'; entityId: number | null; open: boolean }) {
  const { token } = theme.useToken();
  const [offset, setOffset] = useState(0);
  const getUserName = useUserNames();
  const isMobile = useIsMobile();

  useEffect(() => {
    setOffset(0);
  }, [entityId, open]);

  const { data, isLoading } = useQuery<{ history: HistoryEntry[]; total: number }>({
    queryKey: ['entity-history', kind, entityId, offset],
    enabled: open && entityId !== null,
    queryFn: () => {
      const url = kind === 'task' ? `/api/task/${entityId}/history` : `/api/assignment/${entityId}/history`;
      return apiGet(`${url}?offset=${offset}&limit=${HISTORY_PAGE_SIZE}`);
    },
  });

  if (!open) return null;

  return (
    <div
      style={
        isMobile
          ? { width: '100%', borderTop: `1px solid ${token.colorBorder}`, paddingTop: 16, marginTop: 16, maxHeight: 320, overflowY: 'auto' }
          : { width: 300, flexShrink: 0, borderLeft: `1px solid ${token.colorBorder}`, paddingLeft: 16, marginLeft: 16, maxHeight: 520, overflowY: 'auto' }
      }
    >
      <div style={{ fontWeight: 600, marginBottom: 8 }}>История изменений</div>
      {isLoading && <Spin />}
      {data && data.history.length === 0 && <Empty description="Изменений пока нет" image={Empty.PRESENTED_IMAGE_SIMPLE} />}
      {data && data.history.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {data.history.map((entry) => (
            <div key={entry.id} style={{ fontSize: '0.8rem', padding: '6px 10px', background: token.colorFillTertiary, borderRadius: token.borderRadiusSM }}>
              <div style={{ opacity: 0.6, fontSize: '0.72rem' }}>
                {entry.changed_at} — {formatChangedBy(entry)}
              </div>
              <div>{formatHistoryText(entry, getUserName, kind === 'task')}</div>
            </div>
          ))}
        </div>
      )}
      {data && data.total > HISTORY_PAGE_SIZE && (
        <Pagination
          style={{ marginTop: 12, textAlign: 'center' }}
          simple
          showSizeChanger={false}
          current={Math.floor(offset / HISTORY_PAGE_SIZE) + 1}
          pageSize={HISTORY_PAGE_SIZE}
          total={data.total}
          onChange={(page) => setOffset((page - 1) * HISTORY_PAGE_SIZE)}
        />
      )}
    </div>
  );
}
