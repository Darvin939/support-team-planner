import {useEffect, useRef} from 'react';
import dayjs from 'dayjs';
import type {Assignment} from '../../hooks/usePlanningData';
import {copyFontStyle, DRAG_START_THRESHOLD_PX, findScrollableAncestor} from './scrollUtils';
import {API_DATE_FORMAT} from '../../lib/dateFormats';

const SCROLL_ZONE = 60;
const MAX_SPEED = 10;
// Совпадает с ограничением DatePicker'ов (minDate/maxDate) в PlanningPage.tsx.
const MIN_YEAR = 2000;
const MAX_YEAR = 2099;

interface BulkItem {
  assignmentId: number;
  taskId: number;
  date: string;
}

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
  // Заполняется в момент mousedown, если захваченное назначение входит в активную мультивыборку
  // (>1 элемента) — тогда весь drag двигает все элементы снапшота на одну и ту же дельту дней,
  // а не только захваченное назначение.
  bulkSnapshot: BulkItem[] | null;
  bulkValid: boolean;
}

/**
 * Faithful port of the original planning.js setupAssignmentDrag: a raw
 * mousedown/mousemove/mouseup drag (not HTML5 DnD), with a cloned floating
 * ghost clamped to the scrollable area, edge auto-scroll, and
 * elementFromPoint-based drop-target detection so it works regardless of
 * antd Table's internal DOM/sticky-column structure.
 *
 * Также умеет двигать сразу несколько назначений (bulkSnapshot/onDropMany) —
 * см. useAssignmentSelection.ts для того, как формируется мультивыборка.
 */
export function useAssignmentDrag(options: {
  isTaskLocked: (taskId: number) => boolean;
  getOccupant: (taskId: number, date: string) => Assignment | undefined;
  onDrop: (assignmentId: number, taskId: number, newDate: string) => void;
  onDropMany: (moves: { assignmentId: number; taskId: number; newDate: string }[]) => void;
  colors: { success: string; error: string; selected: string };
  selectedAssignmentIds: Set<number>;
  getAssignment: (id: number) => Assignment | undefined;
}) {
  const optionsRef = useRef(options);
  optionsRef.current = options;
  const suppressClickRef = useRef(false);

  useEffect(() => {
    let dragState: DragState | null = null;

    // Ячейка при снятии drag-подсветки (over/invalid/source) возвращается не к пустому
    // boxShadow, а к своему настоящему базовому состоянию — синей рамке, если она всё ещё
    // содержит выбранное назначение. Иначе слепой сброс в '' молча стирает инлайн-стиль,
    // который React больше не переустановит сам (его props для этой ячейки не изменились).
    function restoreBaseline(cell: HTMLElement) {
      const chip = cell.querySelector<HTMLElement>('[data-assignment-id]');
      const assignmentId = chip ? Number(chip.dataset.assignmentId) : null;
      if (assignmentId !== null && optionsRef.current.selectedAssignmentIds.has(assignmentId)) {
        cell.style.boxShadow = `inset 0 0 0 2px ${optionsRef.current.colors.selected}`;
      } else {
        cell.style.boxShadow = '';
      }
    }

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
      if (e.button !== 0) return;
      if (e.ctrlKey || e.metaKey) return; // Ctrl зарезервирован за мультивыделением (useAssignmentSelection)
      const target = e.target as HTMLElement;
      const chip = target.closest('[data-assignment-id]') as HTMLElement | null;
      if (!chip) return;
      const cell = chip.closest('[data-schedule-cell]') as HTMLElement | null;
      if (!cell) return;

      const taskId = Number(cell.dataset.taskId);
      const sourceDate = cell.dataset.date!;
      if (optionsRef.current.isTaskLocked(taskId)) return;

      e.preventDefault();

      const assignmentId = Number(chip.dataset.assignmentId);
      const { selectedAssignmentIds, getAssignment, isTaskLocked } = optionsRef.current;
      let bulkSnapshot: BulkItem[] | null = null;
      if (selectedAssignmentIds.has(assignmentId) && selectedAssignmentIds.size > 1) {
        bulkSnapshot = [];
        selectedAssignmentIds.forEach((id) => {
          const a = getAssignment(id);
          if (a && !isTaskLocked(a.task_id)) {
            bulkSnapshot!.push({ assignmentId: a.id, taskId: a.task_id, date: a.date });
          }
        });
      }

      dragState = {
        assignmentId,
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
        bulkSnapshot,
        bulkValid: false,
      };
    }

    function handleMouseMove(e: MouseEvent) {
      if (!dragState) return;
      const state = dragState;

      const dx = e.pageX - state.startX;
      const dy = e.pageY - state.startY;

      if (!state.dragStarted && Math.sqrt(dx * dx + dy * dy) > DRAG_START_THRESHOLD_PX) {
        state.dragStarted = true;

        const stickyCol = state.sourceCell.closest('tr')?.querySelector('td:first-child') as HTMLElement | null;
        state.stickyWidth = stickyCol ? stickyCol.getBoundingClientRect().width : 300;

        state.sourceCell.classList.add('assignment-drag-source');
        const rowRect = state.sourceCell.closest('tr')!.getBoundingClientRect();
        state.rowCenterY = rowRect.top + rowRect.height / 2;

        const ghost = state.sourceChip.cloneNode(true) as HTMLElement;
        ghost.classList.add('assignment-drag-ghost');
        ghost.style.width = `${state.sourceChip.getBoundingClientRect().width}px`;
        copyFontStyle(ghost, state.sourceChip);
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

      document.querySelectorAll<HTMLElement>('.assignment-drag-over, .assignment-drag-invalid').forEach((c) => {
        c.classList.remove('assignment-drag-over', 'assignment-drag-invalid');
        restoreBaseline(c);
      });

      if (targetDate && targetDate !== state.sourceDate && targetTaskId === state.taskId) {
        const { success, error } = optionsRef.current.colors;
        if (state.bulkSnapshot) {
          const deltaDays = dayjs(targetDate).diff(dayjs(state.sourceDate), 'day');
          const movingIds = new Set(state.bulkSnapshot.map((item) => item.assignmentId));
          const targetCounts = new Map<string, number>();
          const targets = state.bulkSnapshot.map((item) => {
            const shifted = dayjs(item.date).add(deltaDays, 'day');
            const shiftedDate = shifted.format(API_DATE_FORMAT);
            const key = `${item.taskId}-${shiftedDate}`;
            targetCounts.set(key, (targetCounts.get(key) ?? 0) + 1);
            return { item, shifted, shiftedDate, key };
          });
          let allValid = true;
          targets.forEach(({ item, shifted, shiftedDate, key }) => {
            const outOfRange = shifted.year() < MIN_YEAR || shifted.year() > MAX_YEAR;
            const occupant = optionsRef.current.getOccupant(item.taskId, shiftedDate);
            const invalid = outOfRange
              || (targetCounts.get(key) ?? 0) > 1
              || (!!occupant && !movingIds.has(occupant.id));
            if (invalid) allValid = false;
            const cell = document.querySelector<HTMLElement>(
              `[data-schedule-cell][data-task-id="${item.taskId}"][data-date="${shiftedDate}"]`
            );
            if (cell) {
              cell.classList.add(invalid ? 'assignment-drag-invalid' : 'assignment-drag-over');
              cell.style.boxShadow = `inset 0 0 0 2px ${invalid ? error : success}`;
            }
          });
          state.targetDate = targetDate;
          state.targetOccupied = !allValid;
          state.bulkValid = allValid;
        } else {
          const occupied = !!optionsRef.current.getOccupant(state.taskId, targetDate);
          targetCell!.classList.add(occupied ? 'assignment-drag-invalid' : 'assignment-drag-over');
          targetCell!.style.boxShadow = `inset 0 0 0 2px ${occupied ? error : success}`;
          state.targetDate = targetDate;
          state.targetOccupied = occupied;
        }
      } else {
        state.targetDate = null;
        state.targetOccupied = false;
        state.bulkValid = false;
      }
    }

    function handleMouseUp() {
      if (!dragState) return;
      const state = dragState;
      dragState = null;

      if (state.scrollRaf) cancelAnimationFrame(state.scrollRaf);
      if (state.ghost) state.ghost.remove();
      document.querySelectorAll<HTMLElement>('.assignment-drag-over, .assignment-drag-invalid, .assignment-drag-source').forEach((c) => {
        c.classList.remove('assignment-drag-over', 'assignment-drag-invalid', 'assignment-drag-source');
        restoreBaseline(c);
      });

      if (!state.dragStarted) return;

      suppressClickRef.current = true;
      setTimeout(() => {
        suppressClickRef.current = false;
      }, 0);

      if (!state.targetDate) return;

      if (state.bulkSnapshot) {
        if (!state.bulkValid) return;
        const deltaDays = dayjs(state.targetDate).diff(dayjs(state.sourceDate), 'day');
        const moves = state.bulkSnapshot.map((item) => ({
          assignmentId: item.assignmentId,
          taskId: item.taskId,
          newDate: dayjs(item.date).add(deltaDays, 'day').format(API_DATE_FORMAT),
        }));
        optionsRef.current.onDropMany(moves);
      } else if (!state.targetOccupied) {
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
