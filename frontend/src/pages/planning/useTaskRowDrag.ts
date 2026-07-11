import {useEffect, useRef} from 'react';

interface RowInfo {
  id: number;
  mid: number;
  el: HTMLElement;
}

interface DragState {
  taskId: number;
  startX: number;
  startY: number;
  dragStarted: boolean;
  ghost: HTMLElement | null;
  ghostOffsetY: number;
  handleX: number;
  originalOrder: number[];
  otherRows: RowInfo[];
  insertionIndex: number;
  indicator: HTMLElement | null;
  scroller: HTMLElement | null;
}

/**
 * Построчный вертикальный drag-and-drop для переупорядочивания задач в пределах уже
 * загруженной страницы. По духу аналогичен useAssignmentDrag.ts (тот же document-level
 * mousedown/mousemove/mouseup, порог ~5px до начала драга, «призрак» в document.body), но
 * работает по вертикальной оси и оперирует индексом вставки, а не координатой ячейки:
 * порядок строк на странице берётся прямо из DOM (visual order === dataSource order antd
 * Table), поэтому отдельный callback для передачи текущего порядка не нужен.
 *
 * Индикатор вставки — отдельный плавающий элемент поверх всего (как и «призрак»), а не
 * box-shadow на самой строке: у ячеек грида (getCellTint) есть собственный непрозрачный фон,
 * который рисуется поверх box-shadow родительского <tr> и перекрывает индикатор везде, кроме
 * зазоров между ячейками.
 */
export function useTaskRowDrag(options: { onDrop: (newOrder: number[]) => void; color: string }) {
  const optionsRef = useRef(options);
  optionsRef.current = options;

  useEffect(() => {
    let dragState: DragState | null = null;

    function positionIndicator(state: DragState, before: boolean, row: RowInfo) {
      if (!state.indicator || !state.scroller) return;
      const rowRect = row.el.getBoundingClientRect();
      const scrollerRect = state.scroller.getBoundingClientRect();
      const left = Math.max(rowRect.left, scrollerRect.left);
      const right = Math.min(rowRect.right, scrollerRect.right);
      const y = before ? rowRect.top : rowRect.bottom;
      state.indicator.style.left = `${left}px`;
      state.indicator.style.top = `${y}px`;
      state.indicator.style.width = `${Math.max(0, right - left)}px`;
    }

    function handleMouseDown(e: MouseEvent) {
      if (e.button !== 0) return;
      const target = e.target as HTMLElement;
      const handle = target.closest('[data-task-row-handle]') as HTMLElement | null;
      if (!handle) return;
      const taskId = Number(handle.dataset.taskRowId);

      e.preventDefault();

      dragState = {
        taskId,
        startX: e.pageX,
        startY: e.pageY,
        dragStarted: false,
        ghost: null,
        ghostOffsetY: 0,
        handleX: handle.getBoundingClientRect().left,
        originalOrder: [],
        otherRows: [],
        insertionIndex: 0,
        indicator: null,
        scroller: document.querySelector<HTMLElement>('[data-planning-grid] .ant-table-body'),
      };
    }

    function handleMouseMove(e: MouseEvent) {
      if (!dragState) return;
      const state = dragState;

      const dx = e.pageX - state.startX;
      const dy = e.pageY - state.startY;

      if (!state.dragStarted && Math.sqrt(dx * dx + dy * dy) > 5) {
        state.dragStarted = true;

        const rows = Array.from(
          document.querySelectorAll<HTMLElement>('[data-planning-grid] .ant-table-tbody tr[data-task-row-id]')
        );
        state.originalOrder = rows.map((r) => Number(r.dataset.taskRowId));

        const draggedRow = rows.find((r) => Number(r.dataset.taskRowId) === state.taskId) ?? null;
        state.otherRows = rows
          .filter((r) => r !== draggedRow)
          .map((el) => {
            const rect = el.getBoundingClientRect();
            return { id: Number(el.dataset.taskRowId), mid: rect.top + rect.height / 2, el };
          });

        const nameEl = draggedRow?.querySelector<HTMLElement>('[data-task-row-name]');
        const sourceForStyle = nameEl ?? draggedRow;
        const ghost = document.createElement('div');
        ghost.className = 'task-row-drag-ghost';
        ghost.textContent = nameEl?.textContent ?? '';
        ghost.style.borderColor = optionsRef.current.color;
        if (sourceForStyle) {
          const cs = getComputedStyle(sourceForStyle);
          ghost.style.fontFamily = cs.fontFamily;
          ghost.style.fontSize = cs.fontSize;
          ghost.style.fontWeight = cs.fontWeight;
          ghost.style.color = cs.color;
        }
        document.body.appendChild(ghost);
        state.ghostOffsetY = ghost.offsetHeight / 2;
        state.ghost = ghost;

        const indicator = document.createElement('div');
        indicator.className = 'task-row-drag-indicator';
        indicator.style.background = optionsRef.current.color;
        document.body.appendChild(indicator);
        state.indicator = indicator;
      }

      if (!state.dragStarted) return;

      if (state.ghost) {
        state.ghost.style.transform = `translate(${state.handleX}px, ${e.clientY - state.ghostOffsetY}px)`;
      }

      const idx = state.otherRows.filter((r) => e.clientY > r.mid).length;
      state.insertionIndex = idx;

      const before = idx < state.otherRows.length;
      const targetRow = before ? state.otherRows[idx] : state.otherRows[state.otherRows.length - 1];
      if (targetRow) positionIndicator(state, before, targetRow);
    }

    function handleMouseUp() {
      if (!dragState) return;
      const state = dragState;
      dragState = null;

      if (state.ghost) state.ghost.remove();
      if (state.indicator) state.indicator.remove();

      if (!state.dragStarted) return;

      const withoutDragged = state.otherRows.map((r) => r.id);
      const newOrder = [
        ...withoutDragged.slice(0, state.insertionIndex),
        state.taskId,
        ...withoutDragged.slice(state.insertionIndex),
      ];

      if (JSON.stringify(newOrder) !== JSON.stringify(state.originalOrder)) {
        optionsRef.current.onDrop(newOrder);
      }
    }

    document.addEventListener('mousedown', handleMouseDown);
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousedown', handleMouseDown);
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      if (dragState?.ghost) dragState.ghost.remove();
      if (dragState?.indicator) dragState.indicator.remove();
    };
  }, []);
}
