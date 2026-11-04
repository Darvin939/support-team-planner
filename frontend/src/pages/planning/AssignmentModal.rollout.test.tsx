// @vitest-environment jsdom

import {afterEach, beforeAll, describe, expect, it, vi} from 'vitest';
import {cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {App as AntApp} from 'antd';
import type {Task} from '../../domain/types';
import {AssignmentModal} from './AssignmentModal';

const mocks = vi.hoisted(() => ({
  bulk: vi.fn(), save: vi.fn(), isError: false, isLoading: false,
  blocks: [{id: 1, name: 'Первый блок'}, {id: 2, name: 'Второй блок'}],
  templates: [
    {id: 10, name: 'Другой шаблон', segment_id: 1, blocks: [{id: 1, name: 'Первый блок', shift_days: 0}]},
    {id: 20, name: 'Шаблон работы', segment_id: 1, blocks: [{id: 2, name: 'Второй блок', shift_days: 1}]},
    {id: 30, name: 'Пустой', segment_id: 1, blocks: []},
  ],
}));
vi.mock('../../hooks/usePlanningData', () => ({
  useTeamBlocks: () => ({data: mocks.blocks}),
  useTeamTemplates: () => ({data: mocks.templates, isError: mocks.isError, isLoading: mocks.isLoading}),
}));
vi.mock('../../hooks/useSettingsData', () => ({useTeamAssignees: () => ({data: []})}));
vi.mock('../../hooks/useMe', () => ({useMe: () => ({data: {role: 'admin'}})}));
vi.mock('../../hooks/useIsMobile', () => ({useIsMobile: () => false}));
vi.mock('../../hooks/useAssignmentMutations', () => ({
  useSaveAssignmentMutation: () => ({mutate: mocks.save, isPending: false}),
  useBulkSaveAssignmentsMutation: () => ({mutate: mocks.bulk, isPending: false}),
  useDeleteAssignmentMutation: () => ({mutate: vi.fn(), isPending: false}),
}));

beforeAll(() => {
  vi.stubGlobal('ResizeObserver', class {observe() {} unobserve() {} disconnect() {}});
  vi.stubGlobal('matchMedia', vi.fn().mockImplementation(() => ({
    matches: false, addListener: vi.fn(), removeListener: vi.fn(),
    addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
  })));
});
afterEach(() => {cleanup(); vi.clearAllMocks(); mocks.isError = false; mocks.isLoading = false;});

const task: Task = {
  id: 1, name: 'Раскатка', description: null, instruction_url: null, criticality: 'medium',
  task_status: 'new', psi_status: 'not_required', segment_id: 1, segment_name: 'One',
  completion_template_id: 20, completion_template_name: 'Шаблон работы', completed_at: null,
  has_assignments: false, has_active_assignments: false,
};
const freezeDays = new Set<string>();
const assignments: [] = [];
function modal(currentTask: Task, open = true) {
  return <AntApp><AssignmentModal open={open} teamId={1} task={currentTask} date="2026-11-04"
    assignment={null} taskAssignments={assignments} freezeDays={freezeDays}
    onClose={vi.fn()} onTaskCompletionSuggested={vi.fn()}/></AntApp>;
}

describe('saved rollout template in AssignmentModal', () => {
  it('shows the legend without changing manual selection or available blocks', async () => {
    render(modal(task));
    fireEvent.click(screen.getByRole('button', {name: 'Схема раскатки: Раскатка'}));
    const legend = await screen.findByRole('region', {name: 'Схема раскатки: Раскатка'});
    expect(legend.textContent).toContain('Шаблон работы');
    expect(legend.textContent).toContain('Второй блок');
    expect(legend.textContent).not.toContain('Первый блок');
    fireEvent.click(screen.getByRole('button', {name: 'Схема раскатки: Раскатка'}));
    fireEvent.mouseDown(screen.getByRole('combobox', {name: /Блок/}));
    expect(await screen.findByText('Первый блок', {selector: '.ant-select-item-option-content'})).toBeTruthy();
    fireEvent.click(screen.getByText('Первый блок', {selector: '.ant-select-item-option-content'}));
    fireEvent.click(screen.getByRole('button', {name: 'Создать'}));
    await waitFor(() => expect(mocks.save).toHaveBeenCalledWith(expect.objectContaining({block: 'Первый блок'})));
    expect(mocks.bulk).not.toHaveBeenCalled();
  }, 15000);
  it('uses the saved template instead of the first allowed one and submits no template selection', async () => {
    render(modal(task));
    fireEvent.click(screen.getByRole('switch', {name: 'Автоназначение'}));
    expect(await screen.findByText('Второй блок')).not.toBeNull();
    expect(screen.queryByText('Первый блок')).toBeNull();
    expect(screen.queryByRole('combobox', {name: /Шаблон/})).toBeNull();
    fireEvent.click(screen.getByRole('button', {name: 'Создать'}));
    await waitFor(() => expect(mocks.bulk).toHaveBeenCalledWith({assignments: [expect.objectContaining({
      task_id: 1, date: '2026-11-05', block: 'Второй блок', status: 'new',
    })]}));
  });

  it.each([
    [null, 1, 'Укажите шаблон раскатки в работе для автоназначения'],
    [999, 1, 'Шаблон работы недоступен команде или не соответствует сегменту'],
    [20, 2, 'Шаблон работы недоступен команде или не соответствует сегменту'],
    [30, 1, 'В шаблоне работы нет блоков'],
  ] as const)('explains unavailable autoassignment for template %s and segment %s', async (templateId, segmentId, reason) => {
    render(modal({...task, completion_template_id: templateId, segment_id: segmentId}));
    expect((screen.getByRole('switch', {name: 'Автоназначение'}) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(reason)).not.toBeNull();
    expect((screen.getByRole('button', {name: 'Создать'}) as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(screen.getByRole('button', {name: 'Создать'}));
    await waitFor(() => expect(mocks.save).toHaveBeenCalled());
    expect(mocks.bulk).not.toHaveBeenCalled();
  });

  it('distinguishes loading errors from an empty template list', () => {
    mocks.isError = true;
    render(modal(task));
    expect(screen.getByText('Не удалось загрузить шаблон раскатки')).not.toBeNull();
    expect((screen.getByRole('switch', {name: 'Автоназначение'}) as HTMLButtonElement).disabled).toBe(true);
  });

  it('uses the updated task template after closing and reopening', async () => {
    const view = render(modal(task));
    fireEvent.click(screen.getByRole('switch', {name: 'Автоназначение'}));
    expect(await screen.findByText('Второй блок')).not.toBeNull();
    view.rerender(modal(task, false));
    view.rerender(modal({...task, completion_template_id: 10}));
    fireEvent.click(screen.getByRole('switch', {name: 'Автоназначение'}));
    expect(await screen.findByText('Первый блок')).not.toBeNull();
    fireEvent.click(screen.getByRole('button', {name: 'Создать'}));
    await waitFor(() => expect(mocks.bulk).toHaveBeenLastCalledWith({assignments: [expect.objectContaining({
      block: 'Первый блок', date: '2026-11-04',
    })]}));
  });
});
