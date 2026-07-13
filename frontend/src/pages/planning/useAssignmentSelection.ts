import {useEffect, useRef} from 'react';
import {DRAG_START_THRESHOLD_PX, findScrollableAncestor} from './scrollUtils';

const SCROLL_ZONE = 60;
const MAX_SPEED = 10;

interface SelectState {
  startX: number;
  startY: number;
  dragStarted: boolean;
  rect: HTMLElement | null;
  scroller: HTMLElement;
  scrollDir: 'left' | 'right' | null;
  scrollSpeed: number;
  scrollRaf: number | null;
  // ячейка -> id назначения внутри неё, для всех ячеек, сейчас накрытых прямоугольником выделения
  pending: Map<HTMLElement, number>;
}

/**
 * Ctrl+drag поверх грида планирования — выделение прямоугольной областью (лассо) сразу
 * нескольких назначений. Не требует старта на chip'е (можно вести рамку от пустой ячейки).
 * Добавляет назначения в выборку одним коммитом на mouseup — никогда не снимает выделение с уже
 * выбранных элементов (это делает только Ctrl+клик по одному chip'у, см. usePlanningColumns.tsx).
 *
 * Ctrl зарезервирован исключительно за этим хуком — useAssignmentDrag.ts и useTableDragScroll.ts
 * оба игнорируют mousedown, если зажат Ctrl/Cmd.
 */
export function useAssignmentSelection(options: {
  selectedAssignmentIds: Set<number>;
  onCommitSelection: (ids: number[]) => void;
  color: string;
}) {
  const optionsRef = useRef(options);
  optionsRef.current = options;
  const selectSuppressRef = useRef(false);

  useEffect(() => {
    let state: SelectState | null = null;

    function scrollStep() {
      if (!state || !state.scrollDir) return;
      const scroller = state.scroller;
      const speed = state.scrollSpeed;
      if (state.scrollDir === 'left') {
        scroller.scrollLeft = Math.max(0, scroller.scrollLeft - speed);
      } else {
        scroller.scrollLeft = Math.min(scroller.scrollWidth - scroller.clientWidth, scroller.scrollLeft + speed);
      }
      state.scrollRaf = requestAnimationFrame(scrollStep);
    }

    function handleMouseDown(e: MouseEvent) {
      if (e.button !== 0) return;
      if (!(e.ctrlKey || e.metaKey)) return;
      const target = e.target as HTMLElement;
      if (!target.closest('[data-planning-grid]')) return;

      e.preventDefault();

      state = {
        startX: e.clientX,
        startY: e.clientY,
        dragStarted: false,
        rect: null,
        scroller: findScrollableAncestor(target),
        scrollDir: null,
        scrollSpeed: 0,
        scrollRaf: null,
        pending: new Map(),
      };
    }

    function handleMouseMove(e: MouseEvent) {
      if (!state) return;
      const s = state;

      const dx = e.clientX - s.startX;
      const dy = e.clientY - s.startY;

      if (!s.dragStarted && Math.sqrt(dx * dx + dy * dy) > DRAG_START_THRESHOLD_PX) {
        s.dragStarted = true;
        const rectEl = document.createElement('div');
        rectEl.className = 'assignment-select-rect';
        rectEl.style.border = `1px solid ${optionsRef.current.color}`;
        rectEl.style.background = `color-mix(in srgb, ${optionsRef.current.color} 15%, transparent)`;
        document.body.appendChild(rectEl);
        s.rect = rectEl;
      }

      if (!s.dragStarted) return;

      const left = Math.min(s.startX, e.clientX);
      const top = Math.min(s.startY, e.clientY);
      const width = Math.abs(e.clientX - s.startX);
      const height = Math.abs(e.clientY - s.startY);
      if (s.rect) {
        s.rect.style.left = `${left}px`;
        s.rect.style.top = `${top}px`;
        s.rect.style.width = `${width}px`;
        s.rect.style.height = `${height}px`;
      }

      const wRect = s.scroller.getBoundingClientRect();
      const distLeft = e.clientX - wRect.left;
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
      s.scrollDir = scrollDir;
      s.scrollSpeed = scrollSpeed;
      if (scrollDir && !s.scrollRaf) {
        s.scrollRaf = requestAnimationFrame(scrollStep);
      } else if (!scrollDir && s.scrollRaf) {
        cancelAnimationFrame(s.scrollRaf);
        s.scrollRaf = null;
      }

      const right = left + width;
      const bottom = top + height;
      document.querySelectorAll<HTMLElement>('[data-planning-grid] [data-assignment-id]').forEach((chip) => {
        const cell = chip.closest('[data-schedule-cell]') as HTMLElement | null;
        if (!cell) return;
        const assignmentId = Number(chip.dataset.assignmentId);
        // Ячейки, уже входящие в выборку до этого жеста, уже несут постоянную (React-управляемую)
        // подсветку — не трогаем их style.boxShadow вовсе, иначе имитивная очистка на mouseup
        // (см. ниже) молча стирает инлайн-стиль, который React больше не станет переустанавливать
        // сам (его props для этой ячейки не изменились, раз назначение остаётся выбранным).
        const alreadySelected = optionsRef.current.selectedAssignmentIds.has(assignmentId);
        const r = chip.getBoundingClientRect();
        const intersects = r.left < right && r.right > left && r.top < bottom && r.bottom > top;
        if (intersects) {
          if (!s.pending.has(cell)) {
            if (!alreadySelected) {
              cell.classList.add('assignment-lasso-pending');
              cell.style.boxShadow = `inset 0 0 0 2px ${optionsRef.current.color}`;
            }
            s.pending.set(cell, assignmentId);
          }
        } else if (s.pending.has(cell)) {
          if (!alreadySelected) {
            cell.classList.remove('assignment-lasso-pending');
            cell.style.boxShadow = '';
          }
          s.pending.delete(cell);
        }
      });
    }

    function handleMouseUp() {
      if (!state) return;
      const s = state;
      state = null;

      if (s.scrollRaf) cancelAnimationFrame(s.scrollRaf);
      if (s.rect) s.rect.remove();

      const ids = Array.from(s.pending.values());
      s.pending.forEach((assignmentId, cell) => {
        if (optionsRef.current.selectedAssignmentIds.has(assignmentId)) return;
        cell.classList.remove('assignment-lasso-pending');
        cell.style.boxShadow = '';
      });

      if (!s.dragStarted) return;

      selectSuppressRef.current = true;
      setTimeout(() => {
        selectSuppressRef.current = false;
      }, 0);

      if (ids.length > 0) {
        optionsRef.current.onCommitSelection(ids);
      }
    }

    document.addEventListener('mousedown', handleMouseDown);
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousedown', handleMouseDown);
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      if (state?.scrollRaf) cancelAnimationFrame(state.scrollRaf);
      if (state?.rect) state.rect.remove();
    };
  }, []);

  return selectSuppressRef;
}
