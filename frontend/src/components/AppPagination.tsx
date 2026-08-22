import {useEffect} from 'react';
import {Pagination} from 'antd';
import {PAGE_SIZE_OPTIONS} from '../lib/pagination';

export interface AppPaginationProps {
  current: number; pageSize: number; total?: number;
  onChange: (page: number, pageSize: number) => void;
  allowPageSizeChange?: boolean; compact?: boolean;
}

export function AppPagination({current, pageSize, total, onChange,
  allowPageSizeChange = false, compact = false}: AppPaginationProps) {
  const lastPage = total === undefined ? undefined : Math.max(1, Math.ceil(total / pageSize));
  useEffect(() => {
    if (lastPage !== undefined && current > lastPage) onChange(lastPage, pageSize);
  }, [current, lastPage, onChange, pageSize]);
  if (total === undefined || total <= pageSize) return null;
  return <div data-app-pagination data-compact={compact || undefined} style={{textAlign: 'center', marginTop: 16}}>
    <Pagination current={current} pageSize={pageSize} total={total} pageSizeOptions={PAGE_SIZE_OPTIONS}
      showSizeChanger={allowPageSizeChange} size={compact ? 'small' : undefined} onChange={onChange}/>
  </div>;
}
