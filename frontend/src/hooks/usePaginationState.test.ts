import {describe, expect, it} from 'vitest';
import {paginationOffset, paginationPage} from './usePaginationState';

describe('pagination calculations', () => {
  it('converts pages and offsets consistently', () => {
    expect(paginationOffset(1, 20)).toBe(0);
    expect(paginationOffset(3, 20)).toBe(40);
    expect(paginationPage(40, 20)).toBe(3);
  });

  it('maps an offset inside a page to that page', () => {
    expect(paginationPage(39, 20)).toBe(2);
  });
});
