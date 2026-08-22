import {useCallback, useMemo, useState} from 'react';

export const paginationOffset = (page: number, pageSize: number) => (page - 1) * pageSize;

export function usePaginationState(initialPageSize: number) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSizeState] = useState(initialPageSize);
  const offset = useMemo(() => paginationOffset(page, pageSize), [page, pageSize]);
  const reset = useCallback(() => setPage(1), []);
  const setPageSize = useCallback((size: number) => {
    setPageSizeState(size);
    setPage(1);
  }, []);
  const onChange = useCallback((nextPage: number, nextPageSize: number) => {
    if (nextPageSize !== pageSize) setPageSize(nextPageSize);
    else setPage(nextPage);
  }, [pageSize, setPageSize]);

  return useMemo(
    () => ({page, pageSize, offset, setPage, setPageSize, reset, onChange}),
    [page, pageSize, offset, setPageSize, reset, onChange],
  );
}
