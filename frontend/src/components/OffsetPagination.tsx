import type {CSSProperties} from 'react';
import {Pagination} from 'antd';

export function OffsetPagination({offset, pageSize, total, onOffsetChange, simple = true, style}: {
  offset: number;
  pageSize: number;
  total: number;
  onOffsetChange: (offset: number) => void;
  simple?: boolean;
  style?: CSSProperties;
}) {
  if (total <= pageSize) return null;
  return <Pagination style={style} simple={simple} showSizeChanger={false}
    current={Math.floor(offset / pageSize) + 1} pageSize={pageSize} total={total}
    onChange={(page) => onOffsetChange((page - 1) * pageSize)} />;
}
