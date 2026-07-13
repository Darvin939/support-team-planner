import {useEffect, useRef} from 'react';
import {findScrollableAncestor} from './scrollUtils';

interface PanState {
  wrapper: HTMLElement;
  startX: number;
  startY: number;
  startScrollLeft: number;
  dragging: boolean;
}

/**
 * Faithful port of the original planning.js setupDragScroll: click-and-drag
 * anywhere on the grid (except a chip belonging to a non-terminal task, or an
 * interactive control) pans the table horizontally. Yields to
 * useAssignmentDrag's chip-rescheduling drag via the same isTaskLocked check.
 */
export function useTableDragScroll(options: { isTaskLocked: (taskId: number) => boolean }) {
  const optionsRef = useRef(options);
  optionsRef.current = options;
  const suppressClickRef = useRef(false);

  useEffect(() => {
    let state: PanState | null = null;

    function handleMouseDown(e: MouseEvent) {
      if (e.ctrlKey || e.metaKey) return; // Ctrl зарезервирован за мультивыделением (useAssignmentSelection)
      const target = e.target as HTMLElement;
      if (!target.closest('[data-planning-grid]')) return;
      if (target.closest('button, input, select, textarea, a')) return;

      const chip = target.closest('[data-assignment-id]') as HTMLElement | null;
      if (chip) {
        const cell = chip.closest('[data-schedule-cell]') as HTMLElement | null;
        const taskId = cell ? Number(cell.dataset.taskId) : null;
        if (taskId !== null && !optionsRef.current.isTaskLocked(taskId)) return;
      }

      const wrapper = findScrollableAncestor(target);
      state = {
        wrapper,
        startX: e.pageX,
        startY: e.pageY,
        startScrollLeft: wrapper.scrollLeft,
        dragging: false,
      };
    }

    function handleMouseMove(e: MouseEvent) {
      if (!state) return;

      const dx = e.pageX - state.startX;
      const dy = e.pageY - state.startY;

      if (!state.dragging && Math.sqrt(dx * dx + dy * dy) > 5) {
        state.dragging = true;
        state.wrapper.style.cursor = 'grabbing';
        state.wrapper.style.userSelect = 'none';
      }

      if (state.dragging) {
        state.wrapper.scrollLeft = state.startScrollLeft - dx * 1.5;
      }
    }

    function handleMouseUp() {
      if (!state) return;
      const wasDragging = state.dragging;
      state.wrapper.style.cursor = '';
      state.wrapper.style.userSelect = '';
      state = null;

      if (wasDragging) {
        suppressClickRef.current = true;
        setTimeout(() => {
          suppressClickRef.current = false;
        }, 0);
      }
    }

    document.addEventListener('mousedown', handleMouseDown);
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousedown', handleMouseDown);
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, []);

  return suppressClickRef;
}
