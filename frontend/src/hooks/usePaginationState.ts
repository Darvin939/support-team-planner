import {useCallback, useMemo, useState} from 'react';

export function usePaginationState(initialPageSize: number) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSizeState] = useState(initialPageSize);
  const offset = useMemo(() => (page - 1) * pageSize, [page, pageSize]);
  const reset = useCallback(() => setPage(1), []);
  const setPageSize = useCallback((size: number) => {
    setPageSizeState(size);
    setPage(1);
  }, []);
  const setOffset = useCallback((nextOffset: number) => {
    setPage(Math.floor(nextOffset / pageSize) + 1);
  }, [pageSize]);
  const onChange = useCallback((nextPage: number, nextPageSize: number) => {
    if (nextPageSize !== pageSize) setPageSize(nextPageSize);
    else setPage(nextPage);
  }, [pageSize, setPageSize]);

  return useMemo(
    () => ({page, pageSize, offset, setPage, setPageSize, setOffset, reset, onChange}),
    [page, pageSize, offset, setPageSize, setOffset, reset, onChange],
  );
}
