export function findScrollableAncestor(el: HTMLElement): HTMLElement {
  let node: HTMLElement | null = el;
  while (node) {
    if (node.scrollWidth > node.clientWidth) return node;
    node = node.parentElement;
  }
  return el;
}
