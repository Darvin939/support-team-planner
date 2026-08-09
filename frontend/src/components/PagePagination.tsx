import {Pagination} from 'antd';
import {PAGE_SIZE_OPTIONS} from '../lib/pagination';

export interface PagePaginationProps {
  current: number;
  pageSize: number;
  total: number;
  onChange: (page: number, pageSize: number) => void;
}

export function PagePagination({current, pageSize, total, onChange}: PagePaginationProps) {
  if (total <= pageSize) return null;

  return (
    <div style={{textAlign: 'center', marginTop: 16}}>
      <Pagination
        current={current}
        pageSize={pageSize}
        total={total}
        pageSizeOptions={PAGE_SIZE_OPTIONS}
        showSizeChanger
        onChange={onChange}
      />
    </div>
  );
}
