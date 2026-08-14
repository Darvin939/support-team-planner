// @vitest-environment jsdom

import {cleanup, render, screen} from '@testing-library/react';
import {afterEach, beforeAll, describe, expect, it, vi} from 'vitest';
import {PsiStatusBadge, ScheduleChip} from './planningBadges';

beforeAll(() => {
  vi.stubGlobal('matchMedia', vi.fn().mockImplementation((query: string) => ({
    matches: false, media: query, onchange: null,
    addListener: vi.fn(), removeListener: vi.fn(),
    addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
  })));
});

afterEach(cleanup);

describe('PsiStatusBadge', () => {
  it('показывает компактный оранжевый маркер требования ПСИ', () => {
    render(<PsiStatusBadge value="required" compact/>);
    const marker = screen.getByText('Требуется ПСИ');
    expect(marker.getAttribute('data-psi-status-marker')).toBe('required');
    expect(marker.style.fontSize).toBe('0.62rem');
    expect(marker.style.padding).toBe('0px 5px');
  });

  it('показывает прохождение и скрывает необязательное ПСИ', () => {
    const {rerender} = render(<PsiStatusBadge value="passed" compact/>);
    expect(screen.getByText('ПСИ ✓')).toBeTruthy();
    rerender(<PsiStatusBadge value="not_required" compact/>);
    expect(screen.queryByText(/ПСИ/)).toBeNull();
  });
});

describe('ScheduleChip comment', () => {
  const assignment = {
    id: 1,
    block: null,
    status: 'planned' as const,
    user_name: 'Иванов',
    comment: 'Длинный комментарий назначения для отображения в несколько строк',
    time_spent: null,
  };

  it('clamps a comment to three lines and exposes the full text', () => {
    render(<ScheduleChip assignment={assignment}/>);
    const comment = screen.getByText(assignment.comment);
    expect(comment.getAttribute('title')).toBe(assignment.comment);
    expect(comment.style.webkitLineClamp).toBe('3');
    expect(comment.style.overflow).toBe('hidden');
    expect(comment.getAttribute('data-assignment-comment')).not.toBeNull();
  });

  it('does not reserve a comment row when the comment is empty', () => {
    render(<ScheduleChip assignment={{...assignment, comment: null}}/>);
    expect(document.querySelector('[data-assignment-comment]')).toBeNull();
  });
});
