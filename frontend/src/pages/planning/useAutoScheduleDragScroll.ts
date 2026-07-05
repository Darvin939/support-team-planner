import {useEffect, useRef} from 'react';

/**
 * Port of the original planning.js setupAutoScheduleDragScroll: click-and-drag
 * anywhere in the autoschedule mini-grid pans it horizontally (1:1, no bail
 * conditions on mousedown target, unlike the main table). If a real drag
 * happened, the resulting click is swallowed via a capture-phase listener on
 * the wrapper itself, so it never reaches a block badge's onPick or a cell's
 * onPlace handler — mirrors the original's capture-phase stopPropagation trick.
 */
export function useAutoScheduleDragScroll<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);

  useEffect(() => {
    const wrapper = ref.current;
    if (!wrapper) return;

    let isDown = false;
    let dragged = false;
    let startX = 0;
    let startScrollLeft = 0;

    wrapper.style.cursor = 'grab';

    function handleMouseDown(e: MouseEvent) {
      isDown = true;
      dragged = false;
      startX = e.pageX;
      startScrollLeft = wrapper!.scrollLeft;
    }

    function handleMouseMove(e: MouseEvent) {
      if (!isDown) return;
      const walk = e.pageX - startX;
      if (Math.abs(walk) > 5) {
        dragged = true;
        wrapper!.style.cursor = 'grabbing';
        wrapper!.style.userSelect = 'none';
        wrapper!.scrollLeft = startScrollLeft - walk;
      }
    }

    function handleMouseUp() {
      if (!isDown) return;
      isDown = false;
      wrapper!.style.cursor = 'grab';
      wrapper!.style.userSelect = '';
    }

    function handleClickCapture(e: MouseEvent) {
      if (dragged) {
        e.stopPropagation();
        e.preventDefault();
        dragged = false;
      }
    }

    wrapper.addEventListener('mousedown', handleMouseDown);
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    wrapper.addEventListener('click', handleClickCapture, true);

    return () => {
      wrapper.removeEventListener('mousedown', handleMouseDown);
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      wrapper.removeEventListener('click', handleClickCapture, true);
    };
  }, []);

  return ref;
}
