// @vitest-environment jsdom
import {cleanup, render, screen} from '@testing-library/react';
import {afterEach, describe, expect, it} from 'vitest';
import {StatisticsDateCell} from './StatisticsPage';

afterEach(cleanup);

describe('StatisticsDateCell', () => {
  it('keeps the original date node and omits a zero counter', () => {
    const {container} = render(<StatisticsDateCell originNode={<span>18</span>} count={0}/>);
    expect(screen.getByText('18')).toBeTruthy();
    expect(container.querySelector('.statistics-calendar-work-count')).toBeNull();
  });

  it('shows exact values through nine and caps larger values at 9+', () => {
    const {rerender} = render(<StatisticsDateCell originNode={<span>18</span>} count={9}/>);
    expect(screen.getByText('9')).toBeTruthy();

    rerender(<StatisticsDateCell originNode={<span>18</span>} count={10}/>);
    const badge = screen.getByText('9+');
    expect(badge.getAttribute('aria-hidden')).toBe('true');
    expect(badge.closest('button, a')).toBeNull();
  });
});
