import {useEffect, useRef} from 'react';

/** Click-and-drag horizontal panning for date grids. A real drag suppresses the
 * click that would otherwise activate a cell or a badge underneath the pointer. */
export function usePlanningGridDragScroll<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);

  useEffect(() => {
    const wrapper = ref.current;
    if (!wrapper) return;

    let isDown = false;
    let dragged = false;
    let startX = 0;
    let startScrollLeft = 0;
    wrapper.style.cursor = 'grab';

    const handleMouseDown = (event: MouseEvent) => {
      isDown = true;
      dragged = false;
      startX = event.pageX;
      startScrollLeft = wrapper.scrollLeft;
      event.preventDefault();
      document.body.style.userSelect = 'none';
    };
    const handleMouseMove = (event: MouseEvent) => {
      if (!isDown) return;
      const walk = event.pageX - startX;
      if (Math.abs(walk) <= 5) return;
      dragged = true;
      wrapper.style.cursor = 'grabbing';
      wrapper.style.userSelect = 'none';
      wrapper.scrollLeft = startScrollLeft - walk;
    };
    const handleMouseUp = () => {
      if (!isDown) return;
      isDown = false;
      wrapper.style.cursor = 'grab';
      wrapper.style.userSelect = '';
      document.body.style.userSelect = '';
    };
    const handleClickCapture = (event: MouseEvent) => {
      if (!dragged) return;
      event.stopPropagation();
      event.preventDefault();
      dragged = false;
    };
    const handleContextMenu = (event: MouseEvent) => {
      if (!dragged) return;
      event.preventDefault();
      event.stopPropagation();
      dragged = false;
    };

    wrapper.addEventListener('mousedown', handleMouseDown);
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    wrapper.addEventListener('click', handleClickCapture, true);
    wrapper.addEventListener('contextmenu', handleContextMenu, true);
    return () => {
      wrapper.removeEventListener('mousedown', handleMouseDown);
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      wrapper.removeEventListener('click', handleClickCapture, true);
      wrapper.removeEventListener('contextmenu', handleContextMenu, true);
      document.body.style.userSelect = '';
    };
  }, []);

  return ref;
}
