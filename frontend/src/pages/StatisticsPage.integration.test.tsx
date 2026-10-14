// @vitest-environment jsdom
import {act, cleanup, fireEvent, render, screen, waitFor, within} from '@testing-library/react';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {afterEach, beforeAll, beforeEach, describe, expect, it, vi} from 'vitest';

const mocks = vi.hoisted(() => ({get: vi.fn(), teams: [{id: 1, name: 'Поддержка'}, {id: 2, name: 'Разработка'}]}));
vi.mock('../lib/apiMutate', async importOriginal => ({
  ...await importOriginal<typeof import('../lib/apiMutate')>(), apiGet: mocks.get,
}));
vi.mock('../hooks/useTeams', () => ({useTeams: () => ({data: mocks.teams})}));
vi.mock('../hooks/useIsMobile', () => ({useIsMobile: () => false}));
import {StatisticsPage} from './StatisticsPage';

let client: QueryClient;
const scroll = vi.fn();
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(done => { resolve = done; });
  return {promise, resolve};
}
function response(date: string, total = 25) {
  return {
    items: total ? [{id: 1, task_name: `Работа ${date}`, team_name: 'Поддержка', criticality: 'high',
      date, block: 'Утро', status: 'new', user_name: 'Иванов', comment: 'Комментарий'}] : [],
    total, stats: {status: {new: total, planned: 0}, criticality: {high: total, medium: 0, low: 0}},
  };
}
function defaultGet(url: string) {
  const from = new URL(url, 'http://localhost').searchParams.get('start_date')!;
  if (url.includes('active-assignment-counts')) return Promise.resolve([
    {date: `${from.slice(0, 7)}-03`, count: 12}, {date: `${from.slice(0, 7)}-14`, count: 25},
  ]);
  return Promise.resolve(response(from));
}
function mount() {
  client = new QueryClient({defaultOptions: {queries: {retry: false, gcTime: Infinity}}});
  return render(<QueryClientProvider client={client}><StatisticsPage/></QueryClientProvider>);
}
const day = (date: string) => document.querySelector<HTMLButtonElement>(`[data-date="${date}"]`)!;
async function expectDay(date: string) {
  await waitFor(() => expect(day(date)?.getAttribute('aria-pressed')).toBe('true'));
  await screen.findByText(`Работа ${date}`);
}

beforeAll(() => {
  vi.stubGlobal('matchMedia', vi.fn(() => ({matches: false, addListener: vi.fn(), removeListener: vi.fn(),
    addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn()})));
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} });
  Element.prototype.scrollIntoView = scroll;
  const computed = window.getComputedStyle;
  vi.spyOn(window, 'getComputedStyle').mockImplementation(element => computed(element));
});
beforeEach(() => {
  vi.useFakeTimers({toFake: ['Date']});
  vi.setSystemTime(new Date('2026-10-14T12:00:00'));
  localStorage.clear();
  scroll.mockClear();
  mocks.get.mockReset().mockImplementation(defaultGet);
});
afterEach(() => { cleanup(); client?.clear(); vi.useRealTimers(); });

describe('StatisticsPage navigation and requests', () => {
  it('opens today and selects a day without scrolling until the explicit action', async () => {
    mount();
    await expectDay('2026-10-14');
    expect(mocks.get.mock.calls.some(([url]) => url.includes('start_date=2026-10-01') && url.includes('end_date=2026-10-31'))).toBe(true);
    fireEvent.click(day('2026-10-03'));
    await expectDay('2026-10-03');
    expect(scroll).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', {name: 'К списку работ'}));
    expect(scroll).toHaveBeenCalledOnce();
    expect(document.activeElement?.getAttribute('aria-label')).toBe('Список активных работ');
    for (const name of ['Работа', 'Команда', 'Крит.', 'Блок', 'Статус', 'Исполнитель', 'Комментарий']) {
      expect(screen.getByRole('columnheader', {name})).toBeTruthy();
    }
  });

  it('preserves both modes dates and resets pagination when the day changes', async () => {
    localStorage.setItem('filterDateFrom', '2026-09-01');
    localStorage.setItem('filterDateTo', '2026-09-20');
    mount();
    await expectDay('2026-10-14');
    fireEvent.click(screen.getByTitle('2'));
    await waitFor(() => expect(mocks.get.mock.calls.some(([url]) => url.includes('offset=20'))).toBe(true));
    fireEvent.click(day('2026-10-03'));
    await expectDay('2026-10-03');
    expect(mocks.get.mock.calls.filter(([url]) => url.includes('active-assignments') && url.includes('start_date=2026-10-03')).every(([url]) => url.includes('offset=0'))).toBe(true);
    fireEvent.click(screen.getByText('За период', {exact: true}));
    await screen.findByText('Работа 2026-09-01');
    expect(screen.getByRole('columnheader', {name: 'Дата'})).toBeTruthy();
    expect(document.querySelector('[data-date]')).toBeNull();
    expect(document.querySelectorAll('.ant-picker-range input')[0].getAttribute('value')).toBe('01.09.2026');
    fireEvent.click(screen.getByText('По дням', {exact: true}));
    await expectDay('2026-10-03');
    fireEvent.click(screen.getByText('За период', {exact: true}));
    await screen.findByText('Работа 2026-09-01');
  });

  it('selects first active day, first day in empty month, and today on return', async () => {
    mocks.get.mockImplementation((url: string) => url.includes('active-assignment-counts') && url.includes('2026-12-01') ? Promise.resolve([]) : defaultGet(url));
    mount();
    await expectDay('2026-10-14');
    fireEvent.click(screen.getByRole('button', {name: 'Следующий месяц'}));
    await expectDay('2026-11-03');
    fireEvent.click(screen.getByRole('button', {name: 'Следующий месяц'}));
    await expectDay('2026-12-01');
    fireEvent.click(screen.getByRole('button', {name: 'Сегодня'}));
    await expectDay('2026-10-14');
  });

  it('preserves manual selection on pending response and background refresh', async () => {
    const pending = deferred<Array<{date: string; count: number}>>();
    mocks.get.mockImplementation((url: string) => url.includes('active-assignment-counts') && url.includes('2026-11-01') ? pending.promise : defaultGet(url));
    mount();
    await expectDay('2026-10-14');
    fireEvent.click(screen.getByRole('button', {name: 'Следующий месяц'}));
    expect(screen.getByText('Работа 2026-10-14')).toBeTruthy();
    expect(screen.getByRole('heading', {name: 'Работы на 14 октября 2026'})).toBeTruthy();
    expect(document.querySelector('.statistics-details [aria-busy="true"]')).toBeTruthy();
    fireEvent.click(day('2026-11-20'));
    await expectDay('2026-11-20');
    await act(async () => pending.resolve([{date: '2026-11-03', count: 12}]));
    await waitFor(() => expect(day('2026-11-03').getAttribute('aria-label')).toContain('12'));
    await expectDay('2026-11-20');
    await act(async () => { await client.invalidateQueries(); });
    await expectDay('2026-11-20');
  });

  it('retains the table and its old date during day loading, then replaces them together', async () => {
    const pending = deferred<ReturnType<typeof response>>();
    mocks.get.mockImplementation((url: string) => url.includes('active-assignments/') && url.includes('start_date=2026-10-03') ? pending.promise : defaultGet(url));
    mount();
    await expectDay('2026-10-14');
    const table = screen.getByRole('table');
    fireEvent.click(day('2026-10-03'));
    expect(screen.getByRole('table')).toBe(table);
    expect(screen.getByRole('heading', {name: 'Работы на 14 октября 2026'})).toBeTruthy();
    expect(screen.queryByRole('heading', {name: 'Работы на 3 октября 2026'})).toBeNull();
    await act(async () => pending.resolve(response('2026-10-03')));
    await expectDay('2026-10-03');
    expect(screen.getByRole('heading', {name: 'Работы на 3 октября 2026'})).toBeTruthy();
    expect(screen.getByRole('table')).toBe(table);
  });

  it('ignores a late response from a previous month', async () => {
    const pending = deferred<Array<{date: string; count: number}>>();
    mocks.get.mockImplementation((url: string) => url.includes('active-assignment-counts') && url.includes('2026-11-01') ? pending.promise : defaultGet(url));
    mount();
    await expectDay('2026-10-14');
    fireEvent.click(screen.getByRole('button', {name: 'Следующий месяц'}));
    fireEvent.click(screen.getByRole('button', {name: 'Следующий месяц'}));
    await expectDay('2026-12-03');
    await act(async () => pending.resolve([{date: '2026-11-20', count: 99}]));
    await expectDay('2026-12-03');
    expect(screen.queryByText('99')).toBeNull();
  });

  it('keeps selected day on team filtering and hides stale counts during loading', async () => {
    const pending = deferred<Array<{date: string; count: number}>>();
    mocks.get.mockImplementation((url: string) => {
      if (url.includes('team_ids=1')) return url.includes('active-assignment-counts') ? pending.promise : Promise.resolve(response('2026-10-03', 0));
      return defaultGet(url);
    });
    mount();
    await expectDay('2026-10-14');
    fireEvent.click(day('2026-10-03'));
    await expectDay('2026-10-03');
    fireEvent.mouseDown(screen.getByRole('combobox', {name: 'Команды'}));
    fireEvent.click(document.querySelector('.ant-select-item-option[title="Поддержка"]')!);
    await screen.findByText('Нет активных работ');
    expect(day('2026-10-03').getAttribute('aria-pressed')).toBe('true');
    expect(day('2026-10-03').getAttribute('aria-label')).toContain('загрузка');
    await act(async () => pending.resolve([]));
    await waitFor(() => expect(day('2026-10-03').getAttribute('aria-label')).toContain('активных работ — 0'));
    expect(JSON.parse(localStorage.getItem('statsSelectedTeams')!)).toEqual([1]);
    fireEvent.click(screen.getByText('За период', {exact: true}));
    await waitFor(() => expect(mocks.get.mock.calls.some(([url]) => url.includes('active-assignments') && url.includes('team_ids=1') && !url.includes('end_date=2026-10-03'))).toBe(true));
  });

  it('uses new team counts for a pending automatic selection and ignores the old response', async () => {
    const oldTeam = deferred<Array<{date: string; count: number}>>();
    mocks.get.mockImplementation((url: string) => {
      if (url.includes('active-assignment-counts') && url.includes('2026-11-01')) {
        return url.includes('team_ids=1') ? Promise.resolve([{date: '2026-11-18', count: 2}]) : oldTeam.promise;
      }
      return defaultGet(url);
    });
    mount();
    await expectDay('2026-10-14');
    fireEvent.click(screen.getByRole('button', {name: 'Следующий месяц'}));
    fireEvent.mouseDown(screen.getByRole('combobox', {name: 'Команды'}));
    fireEvent.click(document.querySelector('.ant-select-item-option[title="Поддержка"]')!);
    await expectDay('2026-11-18');
    await act(async () => oldTeam.resolve([{date: '2026-11-01', count: 99}]));
    await expectDay('2026-11-18');
    expect(day('2026-11-01').getAttribute('aria-label')).toContain('активных работ — 0');
  });

  it('distinguishes loading, retryable errors and empty successful results', async () => {
    const pending = deferred<ReturnType<typeof response>>();
    mocks.get.mockImplementation((url: string) => url.includes('active-assignment-counts') ? Promise.reject(new Error('offline')) : pending.promise);
    mount();
    await screen.findByText('Не удалось загрузить количество работ по датам');
    expect(screen.getByRole('status', {name: 'Загрузка работ'})).toBeTruthy();
    expect(screen.queryByText('Нет активных работ')).toBeNull();
    mocks.get.mockImplementation((url: string) => url.includes('active-assignment-counts') ? Promise.resolve([]) : Promise.reject(new Error('offline')));
    fireEvent.click(screen.getByRole('button', {name: 'Повторить'}));
    await waitFor(() => expect(day('2026-10-03').getAttribute('aria-label')).toContain('активных работ — 0'));
    fireEvent.click(day('2026-10-03'));
    await screen.findByText('Не удалось загрузить работы');
    expect(screen.queryByText('Нет активных работ')).toBeNull();
    mocks.get.mockImplementation(() => Promise.resolve(response('2026-10-03', 0)));
    fireEvent.click(within(document.querySelector('.statistics-details') as HTMLElement).getByRole('button', {name: 'Повторить'}));
    await screen.findByText('Нет активных работ');
    await act(async () => pending.resolve(response('2026-10-14')));
    expect(screen.queryByText('Работа 2026-10-14')).toBeNull();
  });
});
