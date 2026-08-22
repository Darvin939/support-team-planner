import {useCallback, useEffect, useRef, useState} from 'react';

export function scrollToPlanningTaskRow(taskId: number): boolean {
  const row = document.querySelector<HTMLElement>(
    `[data-planning-grid] .ant-table-tbody tr[data-task-row-id="${taskId}"]`,
  );
  if (!row) return false;
  row.scrollIntoView({behavior: 'smooth', block: 'center'});
  return true;
}

export function useTaskRowHighlight(duration = 2000) {
  const [highlight, setHighlight] = useState<{taskId: number; revision: number} | null>(null);
  const timerRef = useRef<number | null>(null);
  const revisionRef = useRef(0);
  const highlightTask = useCallback((taskId: number) => {
    if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    const revision = ++revisionRef.current;
    setHighlight({taskId, revision});
    timerRef.current = window.setTimeout(() => {
      if (revisionRef.current !== revision) return;
      setHighlight(null);
      timerRef.current = null;
    }, duration);
  }, [duration]);
  useEffect(() => () => {
    if (timerRef.current !== null) window.clearTimeout(timerRef.current);
  }, []);
  return {
    highlightedTaskId: highlight?.taskId ?? null,
    highlightRevision: highlight?.revision ?? 0,
    highlightTask,
  };
}
