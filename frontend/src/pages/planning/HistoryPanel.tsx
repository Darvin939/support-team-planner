import {useEffect, useState} from 'react';
import {Button, theme} from 'antd';
import {useIsMobile} from '../../hooks/useIsMobile';
import {HISTORY_PAGE_SIZE, HistoryEntries, useEntityHistory} from './historyShared';
import {usePaginationState} from '../../hooks/usePaginationState';
import {OffsetPagination} from '../../components/OffsetPagination';


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
  const pagination = usePaginationState(HISTORY_PAGE_SIZE);
  const isMobile = useIsMobile();

  useEffect(() => {
    pagination.reset();
  }, [entityId, open, pagination.reset]);

  const {data, isLoading} = useEntityHistory(kind, entityId, pagination.offset, open);

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
      <HistoryEntries entries={data?.history} loading={isLoading} showAssignmentContext={kind === 'task'} compact emptySimple />
      {data && <OffsetPagination style={{marginTop: 12, textAlign: 'center'}} offset={pagination.offset}
        pageSize={HISTORY_PAGE_SIZE} total={data.total} onOffsetChange={pagination.setOffset} />}
    </div>
  );
}
