// @vitest-environment jsdom
import {cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {afterEach, beforeAll, describe, expect, it, vi} from 'vitest';
import {AppPagination} from './AppPagination';
beforeAll(() => {
  vi.stubGlobal('matchMedia', vi.fn(() => ({
    matches: false, addListener: vi.fn(), removeListener: vi.fn(),
    addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
  })));
});
afterEach(cleanup);
describe('AppPagination', () => {
  it('hides a single page', () => {
    const {container} = render(<AppPagination current={1} pageSize={20} total={20} onChange={vi.fn()}/>);
    expect(container.querySelector('.ant-pagination')).toBeNull();
  });
  it('uses fixed compact mode', () => {
    const {container} = render(<AppPagination current={1} pageSize={20} total={40} compact onChange={vi.fn()}/>);
    expect(container.querySelector('[data-compact="true"]')).not.toBeNull();
    expect(container.querySelector('.ant-pagination-options')).toBeNull();
  });
  it('shows size changer only when allowed', () => {
    const {container} = render(<AppPagination current={1} pageSize={20} total={100} allowPageSizeChange onChange={vi.fn()}/>);
    expect(container.querySelector('.ant-pagination-options')).not.toBeNull();
  });
  it('reports page navigation in the common page-based contract', () => {
    const onChange = vi.fn();
    render(<AppPagination current={1} pageSize={20} total={60} onChange={onChange}/>);
    fireEvent.click(screen.getByTitle('2'));
    expect(onChange).toHaveBeenCalledWith(2, 20);
  });
  it('normalizes a page beyond total', async () => {
    const onChange = vi.fn();
    render(<AppPagination current={4} pageSize={20} total={45} onChange={onChange}/>);
    await waitFor(() => expect(onChange).toHaveBeenCalledWith(3, 20));
  });
});
