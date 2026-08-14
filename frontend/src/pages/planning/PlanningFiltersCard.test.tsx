// @vitest-environment jsdom

import {cleanup, fireEvent, render, screen} from '@testing-library/react';
import dayjs from 'dayjs';
import {afterEach, beforeAll, describe, expect, it, vi} from 'vitest';
import {PlanningFiltersCard} from './PlanningFiltersCard';

beforeAll(() => {
  vi.stubGlobal('ResizeObserver', class {
    observe() {}
    unobserve() {}
    disconnect() {}
  });
  vi.stubGlobal('matchMedia', vi.fn().mockImplementation((query: string) => ({
    matches: false, media: query, onchange: null,
    addListener: vi.fn(), removeListener: vi.fn(),
    addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
  })));
});

afterEach(cleanup);

describe('PlanningFiltersCard task statuses', () => {
  it('offers only current task statuses', () => {
    render(
      <PlanningFiltersCard
        isMobile={false}
        range={[dayjs('2026-08-01'), dayjs('2026-08-31')]}
        onRangeChange={vi.fn()}
        search=""
        setSearch={vi.fn()}
        criticalities={[]}
        setCriticalities={vi.fn()}
        segmentIds={[]}
        setSegmentIds={vi.fn()}
        assignmentStatuses={[]}
        setAssignmentStatuses={vi.fn()}
        taskStatuses={[]}
        setTaskStatuses={vi.fn()}
        segments={[]}
        showCompleted={false}
        setShowCompleted={vi.fn()}
      />,
    );

    const selects = screen.getAllByRole('combobox');
    expect(selects.length).toBe(4);
    fireEvent.mouseDown(selects[3]);

    expect(screen.getByText('Новый')).toBeTruthy();
    expect(screen.getByText('Выполнено')).toBeTruthy();
    expect(screen.getByText('Отменено')).toBeTruthy();
    expect(screen.queryByText('К планированию')).toBeNull();
    expect(screen.queryByText('В работе')).toBeNull();
  });
});
