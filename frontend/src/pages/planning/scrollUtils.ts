/** Общий порог смещения мыши (px), после которого mousedown-драг (useAssignmentDrag/
 * useTaskRowDrag) считается начавшимся, а не обычным кликом. */
export const DRAG_START_THRESHOLD_PX = 5;

/** Копирует шрифтовые стили (fontFamily/fontSize/fontWeight/color) с source на target —
 * используется useAssignmentDrag/useTaskRowDrag при создании плавающего "призрака" драга,
 * чтобы его типографика совпадала с исходным элементом. */
export function copyFontStyle(target: HTMLElement, source: HTMLElement): void {
  const cs = getComputedStyle(source);
  target.style.fontFamily = cs.fontFamily;
  target.style.fontSize = cs.fontSize;
  target.style.fontWeight = cs.fontWeight;
  target.style.color = cs.color;
}

export function findScrollableAncestor(el: HTMLElement): HTMLElement {
  let node: HTMLElement | null = el;
  while (node) {
    if (node.scrollWidth > node.clientWidth) {
      // antd's sticky table header (`sticky` prop) renders as its own scroll
      // container, separate from `.ant-table-body`. antd only mirrors
      // body -> header scroll, not the reverse, so dragging from a header
      // cell must scroll the body instead to keep both in sync.
      if (node.classList.contains('ant-table-header')) {
        const body = node.parentElement?.querySelector<HTMLElement>('.ant-table-body');
        if (body) return body;
      }
      return node;
    }
    node = node.parentElement;
  }
  return el;
}
