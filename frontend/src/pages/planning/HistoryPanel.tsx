import {useEffect} from 'react';
import {HISTORY_PAGE_SIZE, HistoryEntries, useEntityHistory} from './historyShared';
import {usePaginationState} from '../../hooks/usePaginationState';
import {AppPagination} from '../../components/AppPagination';


export function HistoryPanel({kind, entityId, open}: {
  kind: 'task' | 'assignment';
  entityId: number | null;
  open: boolean
}) {
  const pagination = usePaginationState(HISTORY_PAGE_SIZE);

  useEffect(() => {
    pagination.reset();
  }, [entityId, open, pagination.reset]);

  const {data, isLoading} = useEntityHistory(kind, entityId, pagination.offset, open);

  if (!open) return null;

  return (
    <div style={{maxHeight: 520, overflowY: 'auto'}}>
      <HistoryEntries entries={data?.history} loading={isLoading} showAssignmentContext={kind === 'task'} compact
                      emptySimple/>
      {data && <AppPagination compact current={pagination.page} pageSize={pagination.pageSize}
                              total={data.total} onChange={pagination.onChange}/>}
    </div>
  );
}
