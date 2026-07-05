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
