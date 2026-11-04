// @vitest-environment jsdom
import {afterEach, beforeAll, describe, expect, it, vi} from 'vitest';
import {cleanup, fireEvent, render, screen, waitFor, within} from '@testing-library/react';
import {Form} from 'antd';
import type {Task} from '../../domain/types';
import {RolloutLegend, type RolloutTemplatesState} from './RolloutLegend';

afterEach(cleanup);
beforeAll(() => {
  vi.stubGlobal('ResizeObserver', class {observe() {} unobserve() {} disconnect() {}});
  vi.stubGlobal('matchMedia', vi.fn().mockImplementation(() => ({
    matches: false, addListener: vi.fn(), removeListener: vi.fn(),
    addEventListener: vi.fn(), removeEventListener: vi.fn(),
  })));
});
const task = {name: 'Работа', completion_template_id: 2, segment_id: 1} as Task;
const templates: RolloutTemplatesState = {isLoading: false, isError: false, data: [
  {id: 1, segment_id: 1, name: 'Другой шаблон', blocks: []},
  {id: 2, segment_id: 1, name: 'Основной', blocks: [
    {id: 3, name: 'В', shift_days: 1}, {id: 1, name: 'А', shift_days: 0}, {id: 2, name: 'Б', shift_days: 1},
  ]},
]};

describe('RolloutLegend', () => {
  it('opens saved template, groups blocks and does not activate parent', async () => {
    const parent = vi.fn();
    render(<div onClick={parent}><RolloutLegend task={task} templates={templates}/></div>);
    const button = screen.getByRole('button', {name: 'Схема раскатки: Работа'});
    expect(screen.queryByRole('region')).toBeNull();
    fireEvent.click(button);
    const legend = await screen.findByRole('region', {name: 'Схема раскатки: Работа'});
    expect(within(legend).getByText('Основной')).toBeTruthy();
    expect(within(legend).queryByText('Другой шаблон')).toBeNull();
    const stages = within(legend).getAllByRole('listitem');
    expect(stages).toHaveLength(2);
    expect(within(stages[0]).getByText('День 0')).toBeTruthy();
    expect(within(stages[1]).getByText('Б, В')).toBeTruthy();
    fireEvent.click(within(legend).getByText('А'));
    expect(parent).not.toHaveBeenCalled();
    fireEvent.keyDown(button, {key: 'Escape'});
    await waitFor(() => expect(button.getAttribute('aria-expanded')).toBe('false'));
    fireEvent.click(button);
    fireEvent.click(await screen.findByRole('button', {name: 'Закрыть схему раскатки'}));
    await waitFor(() => expect(button.getAttribute('aria-expanded')).toBe('false'));
  });

  it('keeps the information button enabled inside a disabled form', async () => {
    render(<Form disabled><RolloutLegend task={task} templates={templates}/></Form>);
    const button = screen.getByRole('button', {name: 'Схема раскатки: Работа'});
    expect((button as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(button);
    expect(await screen.findByText('Основной')).toBeTruthy();
  });

  it.each([
    [{isLoading: true, isError: false}, task, 'Загрузка шаблона раскатки…'],
    [{isLoading: false, isError: true}, task, 'Не удалось загрузить шаблон раскатки'],
    [templates, {...task, completion_template_id: null}, 'Шаблон раскатки не указан в работе'],
    [templates, {...task, completion_template_id: 9}, 'Шаблон работы недоступен команде или не соответствует сегменту'],
    [templates, {...task, segment_id: 9}, 'Шаблон работы недоступен команде или не соответствует сегменту'],
    [templates, {...task, completion_template_id: 1}, 'В шаблоне нет блоков'],
  ] as const)('explains unavailable or empty data %#', async (state, currentTask, message) => {
    render(<RolloutLegend task={currentTask} templates={state}/>);
    fireEvent.click(screen.getByRole('button', {name: 'Схема раскатки: Работа'}));
    expect(await screen.findByText(message)).toBeTruthy();
  });
});
