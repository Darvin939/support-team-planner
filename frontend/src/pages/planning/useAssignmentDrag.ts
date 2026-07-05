import {useEffect, useRef} from 'react';
import {findScrollableAncestor} from './scrollUtils';

const SCROLL_ZONE = 60;
const MAX_SPEED = 10;

interface DragState {
  assignmentId: number;
  taskId: number;
  sourceDate: string;
  startX: number;
  startY: number;
  ghost: HTMLElement | null;
  dragStarted: boolean;
  targetDate: string | null;
  targetOccupied: boolean;
  rowCenterY: number;
  ghostOffsetX: number;
  ghostOffsetY: number;
  stickyWidth: number;
  scrollDir: 'left' | 'right' | null;
  scrollSpeed: number;
  scrollRaf: number | null;
  scroller: HTMLElement;
  sourceCell: HTMLElement;
  sourceChip: HTMLElement;
}

/**
 * Faithful port of the original planning.js setupAssignmentDrag: a raw
 * mousedown/mousemove/mouseup drag (not HTML5 DnD), with a cloned floating
 * ghost clamped to the scrollable area, edge auto-scroll, and
 * elementFromPoint-based drop-target detection so it works regardless of
 * antd Table's internal DOM/sticky-column structure.
 */
export function useAssignmentDrag(options: {
  isTaskLocked: (taskId: number) => boolean;
  isOccupied: (taskId: number, date: string) => boolean;
  onDrop: (assignmentId: number, taskId: number, newDate: string) => void;
  colors: { success: string; error: string };
}) {
  const optionsRef = useRef(options);
  optionsRef.current = options;
  const suppressClickRef = useRef(false);

  useEffect(() => {
    let dragState: DragState | null = null;

    function scrollStep() {
      if (!dragState || !dragState.scrollDir) return;
      const scroller = dragState.scroller;
      const speed = dragState.scrollSpeed;
      if (dragState.scrollDir === 'left') {
        scroller.scrollLeft = Math.max(0, scroller.scrollLeft - speed);
      } else {
        scroller.scrollLeft = Math.min(scroller.scrollWidth - scroller.clientWidth, scroller.scrollLeft + speed);
      }
      dragState.scrollRaf = requestAnimationFrame(scrollStep);
    }

    function handleMouseDown(e: MouseEvent) {
      const target = e.target as HTMLElement;
      const chip = target.closest('[data-assignment-id]') as HTMLElement | null;
      if (!chip) return;
      const cell = chip.closest('[data-schedule-cell]') as HTMLElement | null;
      if (!cell) return;

      const taskId = Number(cell.dataset.taskId);
      const sourceDate = cell.dataset.date!;
      if (optionsRef.current.isTaskLocked(taskId)) return;

      e.preventDefault();

      dragState = {
        assignmentId: Number(chip.dataset.assignmentId),
        taskId,
        sourceDate,
        startX: e.pageX,
        startY: e.pageY,
        ghost: null,
        dragStarted: false,
        targetDate: null,
        targetOccupied: false,
        rowCenterY: 0,
        ghostOffsetX: 0,
        ghostOffsetY: 0,
        stickyWidth: 300,
        scrollDir: null,
        scrollSpeed: 0,
        scrollRaf: null,
        scroller: findScrollableAncestor(cell),
        sourceCell: cell,
        sourceChip: chip,
      };
    }

    function handleMouseMove(e: MouseEvent) {
      if (!dragState) return;
      const state = dragState;

      const dx = e.pageX - state.startX;
      const dy = e.pageY - state.startY;

      if (!state.dragStarted && Math.sqrt(dx * dx + dy * dy) > 5) {
        state.dragStarted = true;

        const stickyCol = state.sourceCell.closest('tr')?.querySelector('td:first-child') as HTMLElement | null;
        state.stickyWidth = stickyCol ? stickyCol.getBoundingClientRect().width : 300;

        state.sourceCell.classList.add('assignment-drag-source');
        const rowRect = state.sourceCell.closest('tr')!.getBoundingClientRect();
        state.rowCenterY = rowRect.top + rowRect.height / 2;

        const ghost = state.sourceChip.cloneNode(true) as HTMLElement;
        ghost.classList.add('assignment-drag-ghost');
        ghost.style.width = `${state.sourceChip.getBoundingClientRect().width}px`;
        document.body.appendChild(ghost);
        state.ghostOffsetX = ghost.offsetWidth / 2;
        state.ghostOffsetY = ghost.offsetHeight / 2;
        state.ghost = ghost;
      }

      if (!state.dragStarted) return;

      const wRect = state.scroller.getBoundingClientRect();
      const xMin = wRect.left + state.stickyWidth + state.ghostOffsetX;
      const xMax = wRect.right - state.ghostOffsetX;
      const clampedX = Math.max(xMin, Math.min(xMax, e.clientX));

      if (state.ghost) {
        state.ghost.style.transform = `translate(${clampedX - state.ghostOffsetX}px, ${state.rowCenterY - state.ghostOffsetY}px)`;
      }

      const distLeft = e.clientX - (wRect.left + state.stickyWidth);
      const distRight = wRect.right - e.clientX;
      let scrollDir: 'left' | 'right' | null = null;
      let scrollSpeed = 0;
      if (distLeft >= 0 && distLeft < SCROLL_ZONE) {
        scrollDir = 'left';
        scrollSpeed = Math.max(1, Math.round((1 - distLeft / SCROLL_ZONE) * MAX_SPEED));
      } else if (distRight >= 0 && distRight < SCROLL_ZONE) {
        scrollDir = 'right';
        scrollSpeed = Math.max(1, Math.round((1 - distRight / SCROLL_ZONE) * MAX_SPEED));
      }
      state.scrollDir = scrollDir;
      state.scrollSpeed = scrollSpeed;
      if (scrollDir && !state.scrollRaf) {
        state.scrollRaf = requestAnimationFrame(scrollStep);
      } else if (!scrollDir && state.scrollRaf) {
        cancelAnimationFrame(state.scrollRaf);
        state.scrollRaf = null;
      }

      const el = document.elementFromPoint(e.clientX, e.clientY);
      const targetCell = el ? (el.closest('[data-schedule-cell]') as HTMLElement | null) : null;
      const targetDate = targetCell ? targetCell.dataset.date! : null;
      const targetTaskId = targetCell ? Number(targetCell.dataset.taskId) : null;

      document.querySelectorAll('.assignment-drag-over, .assignment-drag-invalid').forEach((c) => {
        c.classList.remove('assignment-drag-over', 'assignment-drag-invalid');
        (c as HTMLElement).style.boxShadow = '';
      });

      if (targetDate && targetDate !== state.sourceDate && targetTaskId === state.taskId) {
        const occupied = optionsRef.current.isOccupied(state.taskId, targetDate);
        const { success, error } = optionsRef.current.colors;
        targetCell!.classList.add(occupied ? 'assignment-drag-invalid' : 'assignment-drag-over');
        targetCell!.style.boxShadow = `inset 0 0 0 2px ${occupied ? error : success}`;
        state.targetDate = targetDate;
        state.targetOccupied = occupied;
      } else {
        state.targetDate = null;
        state.targetOccupied = false;
      }
    }

    function handleMouseUp() {
      if (!dragState) return;
      const state = dragState;
      dragState = null;

      if (state.scrollRaf) cancelAnimationFrame(state.scrollRaf);
      if (state.ghost) state.ghost.remove();
      document.querySelectorAll('.assignment-drag-over, .assignment-drag-invalid, .assignment-drag-source').forEach((c) => {
        c.classList.remove('assignment-drag-over', 'assignment-drag-invalid', 'assignment-drag-source');
        (c as HTMLElement).style.boxShadow = '';
      });

      if (!state.dragStarted) return;

      suppressClickRef.current = true;
      setTimeout(() => {
        suppressClickRef.current = false;
      }, 0);

      if (state.targetDate && !state.targetOccupied) {
        optionsRef.current.onDrop(state.assignmentId, state.taskId, state.targetDate);
      }
    }

    document.addEventListener('mousedown', handleMouseDown);
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousedown', handleMouseDown);
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      if (dragState?.scrollRaf) cancelAnimationFrame(dragState.scrollRaf);
      if (dragState?.ghost) dragState.ghost.remove();
    };
  }, []);

  return suppressClickRef;
}
