import {useEffect, useRef} from 'react';

interface PlanningGridViewKeyOptions {
  teamId: number;
  dateFrom: string;
  dateTo: string;
  search: string;
  showCompleted: boolean;
  page: number;
  pageSize: number;
  criticalities: string[];
  assignmentStatuses: string[];
  taskStatuses: string[];
  segmentIds: number[];
  taskIds: number[];
}

interface PlanningGridTodayCenterOptions {
  today: string;
  isReady: boolean;
  viewKey: string;
  renderKey: string;
}

export function createPlanningGridViewKey(options: PlanningGridViewKeyOptions): string {
  return JSON.stringify([
    options.teamId,
    options.dateFrom,
    options.dateTo,
    options.search,
    options.showCompleted,
    options.page,
    options.pageSize,
    [...options.criticalities].sort(),
    [...options.assignmentStatuses].sort(),
    [...options.taskStatuses].sort(),
    [...options.segmentIds].sort((a, b) => a - b),
    [...options.taskIds].sort((a, b) => a - b),
  ]);
}

function getPlanningGrid(): HTMLElement | null {
  return document.querySelector<HTMLElement>('[data-planning-grid] .ant-table-body');
}

function scrollGridToToday(today: string): number | null {
  const grid = getPlanningGrid();
  const todayCell = document.querySelector<HTMLElement>(`[data-planning-grid] td[data-date="${today}"]`);
  const infoCell = grid?.querySelector<HTMLElement>('td:first-child') ?? null;
  if (!grid || !todayCell || !infoCell) return null;
  grid.scrollLeft = todayCell.offsetLeft - grid.offsetWidth / 2 + todayCell.offsetWidth / 2 - infoCell.offsetWidth / 2;
  return grid.scrollLeft;
}

export function usePlanningGridTodayCenter({
                                             today,
                                             isReady,
                                             viewKey,
                                             renderKey,
                                           }: PlanningGridTodayCenterOptions): void {
  const pendingCenterRef = useRef(true);
  const lastScrollLeftRef = useRef<number | null>(null);

  useEffect(() => {
    pendingCenterRef.current = true;
  }, [viewKey]);

  useEffect(() => {
    if (!isReady) return;
    if (pendingCenterRef.current) {
      const centeredScrollLeft = scrollGridToToday(today);
      if (centeredScrollLeft !== null) {
        lastScrollLeftRef.current = centeredScrollLeft;
        pendingCenterRef.current = false;
      }
      return;
    }

    const grid = getPlanningGrid();
    if (grid && lastScrollLeftRef.current !== null) grid.scrollLeft = lastScrollLeftRef.current;
  }, [isReady, renderKey, today, viewKey]);

  useEffect(() => {
    if (!isReady) return;
    const grid = getPlanningGrid();
    if (!grid) return;
    const rememberScrollPosition = () => {
      lastScrollLeftRef.current = grid.scrollLeft;
    };
    grid.addEventListener('scroll', rememberScrollPosition, {passive: true});
    return () => grid.removeEventListener('scroll', rememberScrollPosition);
  }, [isReady, renderKey]);
}
