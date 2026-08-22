// @vitest-environment jsdom

import {act, renderHook} from '@testing-library/react';
import {afterEach, describe, expect, it, vi} from 'vitest';
import {scrollToPlanningTaskRow, useTaskRowHighlight} from './focusPlanningTask';

describe('фокус строки работы планировщика', () => {
  afterEach(() => document.body.replaceChildren());

  it('прокручивает и подсвечивает найденную строку', () => {
    vi.useFakeTimers();
    document.body.innerHTML = '<div data-planning-grid><table><tbody class="ant-table-tbody"><tr data-task-row-id="7"><td></td></tr></tbody></table></div>';
    const row = document.querySelector('tr') as HTMLElement;
    row.scrollIntoView = vi.fn();
    expect(scrollToPlanningTaskRow(7)).toBe(true);
    expect(row.scrollIntoView).toHaveBeenCalledWith({behavior: 'smooth', block: 'center'});
    vi.useRealTimers();
  });

  it('сообщает об отсутствии строки для fallback-навигации', () => {
    expect(scrollToPlanningTaskRow(99)).toBe(false);
  });

  it('перезапускает подсветку и не позволяет старому таймеру снять новую', () => {
    vi.useFakeTimers();
    vi.clearAllTimers();
    const {result, rerender} = renderHook(() => useTaskRowHighlight(1000));
    act(() => result.current.highlightTask(7));
    expect(result.current.highlightedTaskId).toBe(7);
    const firstRevision = result.current.highlightRevision;
    rerender();
    expect(result.current.highlightedTaskId).toBe(7);
    act(() => vi.advanceTimersByTime(500));
    act(() => result.current.highlightTask(7));
    expect(result.current.highlightRevision).toBeGreaterThan(firstRevision);
    act(() => vi.advanceTimersByTime(500));
    expect(result.current.highlightedTaskId).toBe(7);
    act(() => vi.advanceTimersByTime(499));
    expect(result.current.highlightedTaskId).toBe(7);
    act(() => vi.advanceTimersByTime(1));
    expect(result.current.highlightedTaskId).toBeNull();
    vi.useRealTimers();
  });
});
