// @vitest-environment jsdom
import {cleanup, fireEvent, render, waitFor} from '@testing-library/react';
import {App as AntApp} from 'antd';
import dayjs from 'dayjs';
import {afterEach, beforeAll, describe, expect, it, vi} from 'vitest';

const mocks = vi.hoisted(() => ({
  counts: vi.fn(),
  messageError: vi.fn(),
}));

vi.mock('../hooks/useTeams', () => ({useTeams: () => ({data: []})}));
vi.mock('../hooks/useIsMobile', () => ({useIsMobile: () => false}));
vi.mock('../hooks/useDateRangeFilter', () => ({
  useDateRangeFilter: () => [[dayjs('2026-07-15'), dayjs('2026-08-15')], vi.fn()],
}));
vi.mock('../hooks/usePaginationState', () => ({
  usePaginationState: () => ({
    page: 1, pageSize: 20, offset: 0, reset: vi.fn(), setPageSize: vi.fn(), onChange: vi.fn(),
  }),
}));
vi.mock('../hooks/useStatisticsData', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../hooks/useStatisticsData')>();
  return {
    ...actual,
    useActiveAssignments: () => ({data: undefined}),
    useActiveAssignmentDateCounts: (...args: unknown[]) => mocks.counts(...args),
  };
});

import {StatisticsPage} from './StatisticsPage';

beforeAll(() => {
  vi.stubGlobal('matchMedia', vi.fn(() => ({
    matches: false, addListener: vi.fn(), removeListener: vi.fn(),
    addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
  })));
  vi.stubGlobal('ResizeObserver', class {
    observe() {}
    unobserve() {}
    disconnect() {}
  });
  vi.spyOn(AntApp, 'useApp').mockReturnValue({message: {error: mocks.messageError}} as never);
});

afterEach(() => {
  cleanup();
  mocks.counts.mockReset();
  mocks.messageError.mockReset();
});

describe('StatisticsPage calendar counts integration', () => {
  it('updates the counts query from picker-value navigation and keeps the picker usable', async () => {
    mocks.counts.mockReturnValue({data: [], isError: false, errorUpdatedAt: 0});
    const {container} = render(<StatisticsPage/>);

    expect(mocks.counts).toHaveBeenCalledWith('2026-06-29', '2026-09-06', []);
    const rangeInputs = container.querySelectorAll<HTMLInputElement>('.ant-picker-range input');
    expect(rangeInputs).toHaveLength(2);
    fireEvent.click(rangeInputs[1]);

    const nextButton = await waitFor(() => {
      const button = document.querySelector<HTMLButtonElement>('.ant-picker-header-next-btn');
      expect(button).toBeTruthy();
      return button as HTMLButtonElement;
    });
    fireEvent.click(nextButton);

    await waitFor(() => expect(mocks.counts).toHaveBeenCalledWith('2026-07-27', '2026-10-11', []));
    expect(document.querySelector('.ant-picker-dropdown')).toBeTruthy();
  });

  it('shows one common error while leaving the date picker enabled', async () => {
    mocks.counts.mockReturnValue({data: undefined, isError: true, errorUpdatedAt: 42});
    const {container, rerender} = render(<StatisticsPage/>);

    await waitFor(() => expect(mocks.messageError).toHaveBeenCalledTimes(1));
    expect(container.querySelectorAll('input')[1].hasAttribute('disabled')).toBe(false);

    rerender(<StatisticsPage/>);
    expect(mocks.messageError).toHaveBeenCalledTimes(1);
  });
});
