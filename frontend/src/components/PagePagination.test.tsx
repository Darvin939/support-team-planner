import {describe, expect, it, vi} from 'vitest';
import {Pagination} from 'antd';
import {PAGE_SIZE_OPTIONS} from '../lib/pagination';
import {PagePagination} from './PagePagination';

describe('PagePagination', () => {
  it('uses the shared page sizes and page-size changer', () => {
    const onChange = vi.fn();
    const result = PagePagination({current: 2, pageSize: 20, total: 100, onChange});

    expect(result).not.toBeNull();
    const pagination = result!.props.children;
    expect(pagination.type).toBe(Pagination);
    expect(pagination.props).toMatchObject({
      current: 2,
      pageSize: 20,
      total: 100,
      pageSizeOptions: PAGE_SIZE_OPTIONS,
      showSizeChanger: true,
      onChange,
    });
  });

  it('is hidden when all records fit on one page', () => {
    expect(PagePagination({current: 1, pageSize: 20, total: 20, onChange: vi.fn()})).toBeNull();
  });
});
