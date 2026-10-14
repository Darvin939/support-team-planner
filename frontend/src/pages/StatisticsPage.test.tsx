// @vitest-environment jsdom
import {cleanup, fireEvent, render, screen} from '@testing-library/react';
import dayjs from 'dayjs';
import {afterEach, describe, expect, it, vi} from 'vitest';
import {StatisticsCalendar} from '../components/StatisticsCalendar';

afterEach(cleanup);
const props = {
  month: dayjs('2026-10-01'), selectedDay: '2026-10-14',
  counts: [{date: '2026-10-01', count: 9}, {date: '2026-10-02', count: 10}, {date: '2026-10-03', count: 100}],
  error: false, fetching: false, onRetry: vi.fn(), onNavigate: vi.fn(), onSelect: vi.fn(),
};
describe('StatisticsCalendar', () => {
  it('shows exact accessible counts including zero and a selected date', () => {
    render(<StatisticsCalendar {...props}/>);
    for (const [day, count] of [[1, 9], [2, 10], [3, 100], [4, 0]]) {
      expect(screen.getByRole('button', {name: `${day} октября 2026: активных работ — ${count}`})).toBeTruthy();
    }
    expect(screen.queryByText('9+')).toBeNull();
    expect(document.querySelector('[data-date="2026-10-14"]')?.getAttribute('aria-pressed')).toBe('true');
    expect(document.querySelectorAll('[data-date]')).toHaveLength(31);
  });
  it('keeps days interactive during loading without fabricating zeros', () => {
    const onSelect = vi.fn();
    render(<StatisticsCalendar {...props} counts={undefined} fetching onSelect={onSelect}/>);
    const button = screen.getByRole('button', {name: '3 октября 2026: загрузка количества'});
    button.focus();
    expect(document.activeElement).toBe(button);
    expect(button.getAttribute('type')).toBe('button');
    fireEvent.click(button);
    expect(onSelect).toHaveBeenCalledWith('2026-10-03');
    expect(screen.queryByRole('button', {name: /активных работ — 0/})).toBeNull();
    expect(screen.getByText('Загрузка количества работ…')).toBeTruthy();
  });
  it('shows retryable error instead of cached counts and keeps navigation usable', () => {
    const onRetry = vi.fn();
    const onNavigate = vi.fn();
    render(<StatisticsCalendar {...props} error onRetry={onRetry} onNavigate={onNavigate}/>);
    expect(screen.getByRole('button', {name: '3 октября 2026: количество недоступно'})).toBeTruthy();
    fireEvent.click(screen.getByRole('button', {name: 'Повторить'}));
    expect(onRetry).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole('button', {name: 'Следующий месяц'}));
    expect(onNavigate.mock.calls[0][0].format('YYYY-MM')).toBe('2026-11');
  });
});
