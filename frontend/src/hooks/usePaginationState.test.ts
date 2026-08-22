// @vitest-environment jsdom
import {act, renderHook} from '@testing-library/react';
import {describe, expect, it} from 'vitest';
import {paginationOffset, usePaginationState} from './usePaginationState';

describe('pagination calculations', () => {
  it('converts pages and offsets consistently', () => {
    expect(paginationOffset(1, 20)).toBe(0);
    expect(paginationOffset(3, 20)).toBe(40);
  });

  it('owns page changes and resets the page when size changes', () => {
    const {result} = renderHook(() => usePaginationState(20));
    act(() => result.current.onChange(3, 20));
    expect(result.current).toMatchObject({page: 3, pageSize: 20, offset: 40});

    act(() => result.current.onChange(3, 50));
    expect(result.current).toMatchObject({page: 1, pageSize: 50, offset: 0});
  });

  it('resets only the current page', () => {
    const {result} = renderHook(() => usePaginationState(20));
    act(() => result.current.setPageSize(50));
    act(() => result.current.setPage(4));
    act(() => result.current.reset());
    expect(result.current).toMatchObject({page: 1, pageSize: 50, offset: 0});
  });
});
