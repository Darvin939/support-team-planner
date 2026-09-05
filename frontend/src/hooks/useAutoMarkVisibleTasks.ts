import {useEffect, useRef} from 'react';

const VISIBILITY_THRESHOLD = 0.5;
const VISIBLE_FOR_MS = 1000;
const VISIBILITY_MARKER_ATTRIBUTE = 'data-task-visibility-marker';

export function useAutoMarkVisibleTasks(taskIds: number[], enqueue: (taskIds: number[]) => void, enabled = true) {
  const enqueueRef = useRef(enqueue);
  enqueueRef.current = enqueue;
  const taskKey = taskIds.join(',');

  useEffect(() => {
    if (!enabled || typeof IntersectionObserver === 'undefined') return undefined;
    const timers = new Map<number, ReturnType<typeof setTimeout>>();
    const marked = new Set<number>();
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        const taskId = Number((entry.target as HTMLElement).dataset.taskVisibilityMarker);
        if (!taskId) return;
        const oldTimer = timers.get(taskId);
        if (entry.isIntersecting && entry.intersectionRatio >= VISIBILITY_THRESHOLD && !marked.has(taskId)) {
          if (!oldTimer) {
            timers.set(taskId, setTimeout(() => {
              timers.delete(taskId);
              marked.add(taskId);
              enqueueRef.current([taskId]);
            }, VISIBLE_FOR_MS));
          }
        } else if (oldTimer) {
          clearTimeout(oldTimer);
          timers.delete(taskId);
        }
      });
    }, {threshold: [0, VISIBILITY_THRESHOLD]});

    const markers: HTMLElement[] = [];
    document.querySelectorAll<HTMLElement>('[data-planning-grid] tr[data-task-row-id]').forEach((row) => {
      const firstCell = row.querySelector<HTMLElement>('td');
      if (!firstCell) return;
      const marker = document.createElement('span');
      marker.setAttribute(VISIBILITY_MARKER_ATTRIBUTE, row.dataset.taskRowId ?? '');
      marker.setAttribute('aria-hidden', 'true');
      Object.assign(marker.style, {
        position: 'absolute',
        top: '0',
        bottom: '0',
        left: '0',
        width: '1px',
        pointerEvents: 'none',
      });
      firstCell.append(marker);
      markers.push(marker);
      observer.observe(marker);
    });
    return () => {
      timers.forEach((timer) => clearTimeout(timer));
      observer.disconnect();
      markers.forEach((marker) => marker.remove());
    };
  }, [taskKey, enabled]);
}
