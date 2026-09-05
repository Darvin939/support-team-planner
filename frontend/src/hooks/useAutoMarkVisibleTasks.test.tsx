// @vitest-environment jsdom

import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {act, cleanup, render} from '@testing-library/react';
import {useAutoMarkVisibleTasks} from './useAutoMarkVisibleTasks';

type Entry = {target: Element; isIntersecting: boolean; intersectionRatio: number;
  boundingClientRect: DOMRect; intersectionRect: DOMRect};

class FakeIntersectionObserver {
  static instances: FakeIntersectionObserver[] = [];
  callback: (entries: Entry[]) => void;
  options?: IntersectionObserverInit;
  observed: Element[] = [];
  constructor(callback: (entries: Entry[]) => void, options?: IntersectionObserverInit) {
    this.callback = callback;
    this.options = options;
    FakeIntersectionObserver.instances.push(this);
  }
  observe(element: Element) { this.observed.push(element); }
  disconnect() {}
  emit(entry: Entry) { this.callback([entry]); }
}

function Harness({enqueue}: {enqueue: (ids: number[]) => void}) {
  useAutoMarkVisibleTasks([7], enqueue);
  return <div data-planning-grid><table style={{width: 5000}}><tbody>
    <tr data-task-row-id="7"><td style={{position: 'sticky', left: 0}}>Работа</td></tr>
  </tbody></table></div>;
}

const visibilityMarker = () => document.querySelector<HTMLElement>('[data-task-visibility-marker="7"]')!;

describe('useAutoMarkVisibleTasks', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    FakeIntersectionObserver.instances = [];
    vi.stubGlobal('IntersectionObserver', FakeIntersectionObserver);
  });
  afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); });

  it('отмечает строку после секунды устойчивой видимости', () => {
    const enqueue = vi.fn();
    render(<Harness enqueue={enqueue}/>);
    const observer = FakeIntersectionObserver.instances[0];
    const marker = visibilityMarker();
    expect(observer.observed).toEqual([marker]);
    act(() => observer.emit({target: marker, isIntersecting: true, intersectionRatio: 0.5,
      boundingClientRect: {height: 0, width: 0} as DOMRect, intersectionRect: {height: 0, width: 0} as DOMRect}));
    act(() => { vi.advanceTimersByTime(999); });
    expect(enqueue).not.toHaveBeenCalled();
    act(() => { vi.advanceTimersByTime(1); });
    expect(enqueue).toHaveBeenCalledWith([7]);
  });

  it('отменяет таймер, если строка вышла из viewport до секунды', () => {
    const enqueue = vi.fn();
    render(<Harness enqueue={enqueue}/>);
    const observer = FakeIntersectionObserver.instances[0];
    const marker = visibilityMarker();
    act(() => observer.emit({target: marker, isIntersecting: true, intersectionRatio: 0.8,
      boundingClientRect: {height: 0, width: 0} as DOMRect, intersectionRect: {height: 0, width: 0} as DOMRect}));
    act(() => { vi.advanceTimersByTime(500); });
    act(() => observer.emit({target: marker, isIntersecting: false, intersectionRatio: 0,
      boundingClientRect: {height: 0, width: 0} as DOMRect, intersectionRect: {height: 0, width: 0} as DOMRect}));
    act(() => { vi.advanceTimersByTime(1000); });
    expect(enqueue).not.toHaveBeenCalled();
  });

  it('начинает отсчёт, когда ручная прокрутка доводит видимость строки до 50%', () => {
    const enqueue = vi.fn();
    render(<Harness enqueue={enqueue}/>);
    const observer = FakeIntersectionObserver.instances[0];
    const marker = visibilityMarker();
    expect(observer.options?.threshold).toEqual([0, 0.5]);

    act(() => observer.emit({target: marker, isIntersecting: true, intersectionRatio: 0.25,
      boundingClientRect: {height: 40, width: 100} as DOMRect,
      intersectionRect: {height: 10, width: 100} as DOMRect}));
    act(() => { vi.advanceTimersByTime(1000); });
    expect(enqueue).not.toHaveBeenCalled();

    act(() => observer.emit({target: marker, isIntersecting: true, intersectionRatio: 0.5,
      boundingClientRect: {height: 40, width: 100} as DOMRect,
      intersectionRect: {height: 20, width: 100} as DOMRect}));
    act(() => { vi.advanceTimersByTime(1000); });
    expect(enqueue).toHaveBeenCalledWith([7]);
  });

  it('отменяет отсчёт, когда при ручной прокрутке видимость падает ниже 50%', () => {
    const enqueue = vi.fn();
    render(<Harness enqueue={enqueue}/>);
    const observer = FakeIntersectionObserver.instances[0];
    const marker = visibilityMarker();

    act(() => observer.emit({target: marker, isIntersecting: true, intersectionRatio: 0.5,
      boundingClientRect: {height: 40, width: 100} as DOMRect,
      intersectionRect: {height: 20, width: 100} as DOMRect}));
    act(() => { vi.advanceTimersByTime(500); });
    act(() => observer.emit({target: marker, isIntersecting: true, intersectionRatio: 0.25,
      boundingClientRect: {height: 40, width: 100} as DOMRect,
      intersectionRect: {height: 10, width: 100} as DOMRect}));
    act(() => { vi.advanceTimersByTime(1000); });
    expect(enqueue).not.toHaveBeenCalled();
  });

  it('удаляет служебный маркер при cleanup', () => {
    const {unmount} = render(<Harness enqueue={vi.fn()}/>);
    expect(visibilityMarker()).toBeTruthy();
    unmount();
    expect(document.querySelector('[data-task-visibility-marker]')).toBeNull();
  });
});
