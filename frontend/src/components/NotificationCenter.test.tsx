// @vitest-environment jsdom

import {afterEach, describe, expect, it, vi} from 'vitest';
import {act, cleanup, fireEvent, render, renderHook, screen} from '@testing-library/react';
import {NotificationTabPanel, useDeferredDrawerNavigation} from './NotificationCenter';

describe('общий каркас вкладки уведомлений', () => {
  afterEach(cleanup);

  it('единообразно показывает количество и переданные действия', () => {
    const onClick = vi.fn();
    render(<NotificationTabPanel shown={2} total={12} emptyText="Пусто"
      actions={[{label: 'Показать все', onClick}]}><span>Записи</span></NotificationTabPanel>);
    expect(screen.getByText('Показаны первые 2 из 12')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', {name: 'Показать все'}));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('выполняет переход только после полного закрытия Drawer', () => {
    const closeDrawer = vi.fn();
    const navigate = vi.fn();
    const {result} = renderHook(() => useDeferredDrawerNavigation(closeDrawer, navigate));
    act(() => result.current.selectFromDrawer(42));
    expect(closeDrawer).toHaveBeenCalledOnce();
    expect(navigate).not.toHaveBeenCalled();
    act(() => result.current.afterOpenChange(false));
    expect(navigate).toHaveBeenCalledWith(42);
  });
});
