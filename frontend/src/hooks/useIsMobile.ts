import {useEffect, useState} from 'react';

/** Tracks whether the viewport is at or below `breakpointPx` (default 770, matching 3x-ui's own breakpoint). */
export function useIsMobile(breakpointPx = 770): boolean {
  const [isMobile, setIsMobile] = useState(() => window.matchMedia(`(max-width: ${breakpointPx}px)`).matches);

  useEffect(() => {
    const mql = window.matchMedia(`(max-width: ${breakpointPx}px)`);
    const handleChange = () => setIsMobile(mql.matches);
    handleChange();
    mql.addEventListener('change', handleChange);
    return () => mql.removeEventListener('change', handleChange);
  }, [breakpointPx]);

  return isMobile;
}
