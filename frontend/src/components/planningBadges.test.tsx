// @vitest-environment jsdom

import {cleanup, render, screen} from '@testing-library/react';
import {afterEach, beforeAll, describe, expect, it, vi} from 'vitest';
import {PsiStatusBadge} from './planningBadges';

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
