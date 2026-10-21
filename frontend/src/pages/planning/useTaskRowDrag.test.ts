// @vitest-environment jsdom

import {act, cleanup, renderHook} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {useTaskRowDrag} from './useTaskRowDrag';

afterEach(() => {
  cleanup();
  document.body.replaceChildren();
  vi.restoreAllMocks();
});

beforeEach(() => {
  Object.defineProperty(window, 'scrollTo', {configurable: true, value: vi.fn()});
});

function createGrid() {
  document.body.innerHTML = `
    <div data-planning-grid>
      <div class="ant-table-body">
        <table><tbody class="ant-table-tbody">
          <tr data-task-row-id="1"><td><button data-task-row-handle data-task-row-id="1">A</button><span data-task-row-name>A</span></td></tr>
          <tr data-task-row-id="2"><td><span data-task-row-name>B</span></td></tr>
          <tr data-task-row-id="3"><td><span data-task-row-name>C</span></td></tr>
        </tbody></table>
      </div>
    </div>`;

  const scroller = document.querySelector<HTMLElement>('.ant-table-body')!;
  const rows = Array.from(document.querySelectorAll<HTMLElement>('tr[data-task-row-id]'));
  let scrollOffset = 0;
  rows.forEach((row, index) => {
    const top = index * 100;
    row.getBoundingClientRect = () => ({
      x: 0,
      y: top - scrollOffset,
      top: top - scrollOffset,
      right: 500,
      bottom: top - scrollOffset + 40,
      left: 0,
      width: 500,
      height: 40,
      toJSON: () => ({}),
    });
  });
  scroller.getBoundingClientRect = () => ({
    x: 0, y: 0, top: 0, right: 500, bottom: 400, left: 0, width: 500, height: 400,
    toJSON: () => ({}),
  });

  return {scroller, setScrollOffset: (value: number) => { scrollOffset = value; }};
}

function beginDrag() {
  const handle = document.querySelector<HTMLElement>('[data-task-row-handle]')!;
  handle.dispatchEvent(new MouseEvent('mousedown', {bubbles: true, button: 0, clientX: 10, clientY: 20}));
  document.dispatchEvent(new MouseEvent('mousemove', {bubbles: true, clientX: 10, clientY: 180}));
}

describe('useTaskRowDrag', () => {
  it('обновляет место вставки и порядок после прокрутки без движения указателя', async () => {
    const {scroller, setScrollOffset} = createGrid();
    const onDrop = vi.fn();
    renderHook(() => useTaskRowDrag({onDrop, color: '#1677ff'}));

    act(() => beginDrag());
    expect(document.querySelector('.task-row-drag-indicator')?.getAttribute('style')).toContain('top: 200px');

    act(() => {
      setScrollOffset(120);
      scroller.dispatchEvent(new Event('scroll'));
    });

    expect(document.querySelector('.task-row-drag-indicator')?.getAttribute('style')).toContain('top: 120px');
    await act(async () => {
      document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
      await Promise.resolve();
    });
    expect(onDrop).toHaveBeenCalledWith([2, 3, 1]);
  });

  it.each([['успешного сохранения', false], ['ошибки сохранения', true]])(
    'восстанавливает положение окна и таблицы после %s', async (_label, fails) => {
    const {scroller} = createGrid();
    const scrollTo = vi.fn();
    Object.defineProperty(window, 'scrollX', {configurable: true, value: 12});
    Object.defineProperty(window, 'scrollY', {configurable: true, value: 450});
    Object.defineProperty(window, 'scrollTo', {configurable: true, value: scrollTo});
    scroller.scrollLeft = 55;
    const onDrop = vi.fn(() => fails ? Promise.reject(new Error('Не удалось сохранить')) : Promise.resolve());
    renderHook(() => useTaskRowDrag({onDrop, color: '#1677ff'}));

    act(() => {
      beginDrag();
      document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(scrollTo).toHaveBeenCalledWith(12, 450);
    expect(scroller.scrollLeft).toBe(55);
    },
  );
});
