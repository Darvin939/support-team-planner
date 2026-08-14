// @vitest-environment jsdom

import {cleanup, render, screen} from '@testing-library/react';
import {afterEach, describe, expect, it} from 'vitest';
import {TaskNameWithCriticality} from './TaskNameWithCriticality';

afterEach(cleanup);

describe('TaskNameWithCriticality', () => {
  it('keeps the criticality badge in the same inline flow as a wrapping task name', () => {
    const name = 'Очень длинное название работы, которое переносится на несколько строк';
    render(<TaskNameWithCriticality name={name} criticality="high"/>);

    const title = screen.getByText(name);
    const criticality = title.querySelector<HTMLElement>('[data-task-row-criticality]');

    expect(criticality).not.toBeNull();
    expect(criticality?.parentElement).toBe(title);
    expect(criticality?.style.display).toBe('inline-block');
    expect(criticality?.style.whiteSpace).toBe('nowrap');
    expect(title.style.display).toBe('');
    expect(screen.getByText('В')).toBeTruthy();
  });
});
