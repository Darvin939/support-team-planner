// @vitest-environment jsdom

import {afterEach, beforeAll, describe, expect, it, vi} from 'vitest';
import {cleanup, fireEvent, render, screen, waitFor, within} from '@testing-library/react';
import type {Task} from '../../domain/types';
import {TaskModal} from './TaskModal';
import type {ApiResult} from '../../lib/apiMutate';

const mocks = vi.hoisted(() => ({
  save: vi.fn(),
  saved: undefined as undefined | ((result: ApiResult) => void),
  remove: vi.fn(),
  timeline: vi.fn(),
  timelineData: [] as Array<{date: string; block: string; status: string}>,
  activeTasks: [
    {
      id: 2,
      name: 'Зависимость Альфа',
      criticality: 'high',
      task_status: 'new',
    },
    {
      id: 3,
      name: 'Зависимость Бета',
      criticality: 'low',
      task_status: 'new',
    },
  ],
  segments: [{id: 10, name: 'Основной сегмент'}, {id: 11, name: 'Второй сегмент'}],
  templates: [{id: 20, name: 'Основная раскатка', segment_id: 10, blocks: []},
    {id: 21, name: 'Другая раскатка', segment_id: 11, blocks: []}],
}));

vi.mock('../../hooks/usePlanningData', () => ({
  useTeamTemplates: () => ({data: mocks.templates, isLoading: false, isError: false}),
  useActiveTasksList: () => ({
    data: mocks.activeTasks,
    isLoading: false,
  }),
  useTaskAssignmentTimeline: (taskId: number | null, enabled: boolean) => {
    mocks.timeline(taskId, enabled);
    return {data: mocks.timelineData, isLoading: false, isError: false};
  },
}));

vi.mock('../../hooks/useMe', () => ({useMe: () => ({data: {role: 'admin'}})}));
vi.mock('../../hooks/useSettingsData', () => ({
  useSegments: () => ({data: mocks.segments}),
}));
vi.mock('../../hooks/useDebouncedValue', () => ({useDebouncedValue: (value: string) => value}));
vi.mock('../../hooks/useIsMobile', () => ({useIsMobile: () => false}));
vi.mock('../../hooks/useTaskMutations', () => ({
  useSaveTaskMutation: (onSuccess: (result: ApiResult) => void) => {
    mocks.saved = onSuccess;
    return {mutate: mocks.save, isPending: false};
  },
  useDeleteTaskMutation: () => ({mutate: mocks.remove, isPending: false}),
}));
vi.mock('./HistoryPanel', () => ({
  HistoryPanel: () => null,
  HistoryToggleButton: () => null,
  useHistoryToggle: () => [false, vi.fn()],
}));

beforeAll(() => {
  vi.stubGlobal('ResizeObserver', class {
    observe() {}
    unobserve() {}
    disconnect() {}
  });
  vi.stubGlobal('matchMedia', vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })));
});

afterEach(() => {
  cleanup();
  mocks.save.mockReset();
  mocks.remove.mockReset();
  mocks.timeline.mockReset();
  mocks.timelineData = [];
});

const task: Task = {
  id: 1,
  name: 'Тестовая работа',
  description: 'Подробное описание',
  instruction_url: 'https://example.test/instruction',
  criticality: 'medium',
  task_status: 'new',
  psi_status: 'not_required',
  segment_id: 10,
  segment_name: 'Основной сегмент',
  completion_template_id: 20,
  completion_template_name: 'Основная раскатка',
  completed_at: null,
  has_active_assignments: false,
  has_assignments: false,
};

function renderModal(existingDepIds = [2], modalTask: Task = task) {
  return render(
    <TaskModal open teamId={7} task={modalTask} existingDepIds={existingDepIds} onClose={vi.fn()}/>,
  );
}

describe('TaskModal', () => {
  it('forwards completion after saving a template and closes the form', () => {
    const receive = vi.fn();
    const close = vi.fn();
    render(<TaskModal open={false} teamId={7} task={task} existingDepIds={[]}
      onClose={close} onTaskCompletionSuggested={receive}/>);
    const response = {task_completion_suggestion: {task_id: 1, task_name: task.name}};
    mocks.saved?.(response);
    expect(receive).toHaveBeenCalledWith(response);
    expect(close).toHaveBeenCalledOnce();
  });
  it('clears validation errors when reopening an untouched empty form and validates again on submit', async () => {
    const dependencies: number[] = [];
    const onClose = vi.fn();
    const view = render(<TaskModal open teamId={7} task={null} existingDepIds={dependencies} onClose={onClose}/>);
    fireEvent.click(screen.getByRole('button', {name: 'Создать'}));
    expect(await screen.findByText('Введите имя', {selector: '.ant-form-item-explain-error'})).not.toBeNull();
    expect(document.querySelectorAll('.ant-form-item-has-error').length).toBeGreaterThan(0);

    view.rerender(<TaskModal open={false} teamId={7} task={null} existingDepIds={dependencies} onClose={onClose}/>);
    view.rerender(<TaskModal open teamId={7} task={null} existingDepIds={dependencies} onClose={onClose}/>);
    await waitFor(() => expect(document.querySelectorAll('.ant-form-item-has-error').length).toBe(0));
    expect((screen.getByRole('textbox', {name: 'Имя'}) as HTMLInputElement).value).toBe('');
    expect((screen.getByRole('combobox', {name: 'Сегмент'}) as HTMLInputElement).value).toBe('');
    expect(mocks.save).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', {name: 'Создать'}));
    expect(await screen.findByText('Введите имя', {selector: '.ant-form-item-explain-error'})).not.toBeNull();
    expect(mocks.save).not.toHaveBeenCalled();
  });

  it('groups criticality with PSI and segment with template without extra headings', () => {
    renderModal([]);
    const parameters = screen.getByRole('group', {name: 'Параметры работы'});
    const rollout = screen.getByRole('group', {name: 'Параметры раскатки'});
    expect(within(parameters).getByRole('combobox', {name: 'Критичность'})).not.toBeNull();
    expect(within(parameters).getByRole('checkbox', {name: 'Требуется ПСИ'})).not.toBeNull();
    expect(within(parameters).queryByRole('combobox', {name: 'Сегмент'})).toBeNull();
    expect(within(rollout).getByRole('combobox', {name: 'Сегмент'})).not.toBeNull();
    expect(within(rollout).getByRole('combobox', {name: 'Шаблон раскатки'})).not.toBeNull();
    expect(parameters.compareDocumentPosition(rollout) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(parameters).queryByRole('heading')).toBeNull();
    expect(within(rollout).queryByRole('heading')).toBeNull();
  });

  it('clears the previous template when the segment changes and saves the new pair', async () => {
    renderModal([]);
    const segment = screen.getByRole('combobox', {name: 'Сегмент'});
    fireEvent.mouseDown(segment.closest('.ant-select')!.querySelector('.ant-select-content')!);
    fireEvent.click(await screen.findByText('Второй сегмент', {selector: '.ant-select-item-option-content'}));
    fireEvent.click(screen.getByRole('button', {name: 'Обновить'}));
    expect(await screen.findByText('Выберите шаблон раскатки', {selector: '.ant-form-item-explain-error'})).not.toBeNull();
    expect(mocks.save).not.toHaveBeenCalled();
    const template = screen.getByRole('combobox', {name: 'Шаблон раскатки'});
    fireEvent.mouseDown(template.closest('.ant-select')!.querySelector('.ant-select-content')!);
    fireEvent.click(await screen.findByText('Другая раскатка', {selector: '.ant-select-item-option-content'}));
    fireEvent.click(screen.getByRole('button', {name: 'Обновить'}));
    await waitFor(() => expect(mocks.save).toHaveBeenCalledWith(expect.objectContaining({
      segment_id: 11, completion_template_id: 21,
    })));
  });

  it('requires an explicit segment and template for a new task and submits the selection', async () => {
    render(<TaskModal open teamId={7} task={null} existingDepIds={[]} onClose={vi.fn()}/>);
    const segment = screen.getByRole('combobox', {name: 'Сегмент'}) as HTMLInputElement;
    const template = screen.getByRole('combobox', {name: 'Шаблон раскатки'}) as HTMLInputElement;
    expect(segment.value).toBe('');
    expect(template.disabled).toBe(true);
    fireEvent.change(screen.getByRole('textbox', {name: 'Имя'}), {target: {value: 'Новая работа'}});
    fireEvent.click(screen.getByRole('button', {name: 'Создать'}));
    expect(await screen.findByText('Выберите сегмент', {selector: '.ant-form-item-explain-error'})).not.toBeNull();
    expect(mocks.save).not.toHaveBeenCalled();
    fireEvent.mouseDown(segment.closest('.ant-select')!.querySelector('.ant-select-content')!);
    fireEvent.click(await screen.findByText('Основной сегмент', {selector: '.ant-select-item-option-content'}));
    await waitFor(() => expect(template.disabled).toBe(false));
    fireEvent.mouseDown(template.closest('.ant-select')!.querySelector('.ant-select-content')!);
    expect(screen.queryByText('Другая раскатка', {selector: '.ant-select-item-option-content'})).toBeNull();
    fireEvent.click(await screen.findByText('Основная раскатка', {selector: '.ant-select-item-option-content'}));
    fireEvent.click(screen.getByRole('button', {name: 'Создать'}));
    await waitFor(() => expect(mocks.save).toHaveBeenCalledWith(expect.objectContaining({
      name: 'Новая работа', segment_id: 10, completion_template_id: 20,
    })));
  });

  it('locks segment and template for any assignments and unlocks when none remain', async () => {
    const view = renderModal([], {...task, has_assignments: true});
    expect((screen.getByRole('combobox', {name: 'Сегмент'}) as HTMLInputElement).disabled).toBe(true);
    expect((screen.getByRole('combobox', {name: 'Шаблон раскатки'}) as HTMLInputElement).disabled).toBe(true);
    view.rerender(<TaskModal open teamId={7} task={task} existingDepIds={[]} onClose={vi.fn()}/>);
    expect((screen.getByRole('combobox', {name: 'Сегмент'}) as HTMLInputElement).disabled).toBe(false);
    await waitFor(() => expect((screen.getByRole('combobox', {name: 'Шаблон раскатки'}) as HTMLInputElement).disabled).toBe(false));
  });

  it('allows initial template selection for a legacy task with assignments and other edits without it', async () => {
    renderModal([], {...task, completion_template_id: null, completion_template_name: null, has_assignments: true});
    expect((screen.getByRole('combobox', {name: 'Сегмент'}) as HTMLInputElement).disabled).toBe(true);
    await waitFor(() => expect((screen.getByRole('combobox', {name: 'Шаблон раскатки'}) as HTMLInputElement).disabled).toBe(false));
    fireEvent.click(screen.getByRole('button', {name: 'Обновить'}));
    await waitFor(() => expect(mocks.save).toHaveBeenCalledWith(expect.objectContaining({completion_template_id: null})));
  });

  it('shows the assignment timeline for an active task in the main tab', () => {
    mocks.timelineData = [{date: '2026-09-01', block: 'Анализ', status: 'success'}];
    renderModal();

    expect(screen.getByText('Назначения:')).not.toBeNull();
    expect(screen.getByText('Анализ')).not.toBeNull();
    expect(screen.getByText('Успешно')).not.toBeNull();
    expect(mocks.timeline).toHaveBeenCalledWith(task.id, true);
  });

  it('does not load a timeline for a closed card or a new task', () => {
    const view = renderModal();
    view.rerender(<TaskModal open={false} teamId={7} task={task} existingDepIds={[2]} onClose={vi.fn()}/>);
    expect(mocks.timeline).toHaveBeenLastCalledWith(task.id, false);

    view.rerender(<TaskModal open teamId={7} task={null} existingDepIds={[]} onClose={vi.fn()}/>);
    expect(mocks.timeline).toHaveBeenLastCalledWith(null, false);
    expect(screen.queryByText('Назначения:')).toBeNull();
  });

  it('opens on the main tab and shows the selected dependency count', async () => {
    const view = renderModal();

    expect(screen.getByRole('tab', {name: 'Основное'}).getAttribute('aria-selected')).toBe('true');
    expect(screen.getByRole('tab', {name: 'Зависимости (1)'})).not.toBeNull();
    expect((screen.getByRole('textbox', {name: 'Ссылка на инструкцию'}) as HTMLInputElement).value)
      .toBe('https://example.test/instruction');

    fireEvent.click(screen.getByRole('tab', {name: 'Зависимости (1)'}));
    expect((screen.getByRole('checkbox', {name: /Зависимость Альфа/}) as HTMLInputElement).checked).toBe(true);
    fireEvent.click(screen.getByRole('checkbox', {name: /Зависимость Бета/}));
    expect(screen.getByRole('tab', {name: 'Зависимости (2)'})).not.toBeNull();

    fireEvent.click(screen.getByRole('tab', {name: 'Основное'}));
    view.rerender(<TaskModal open={false} teamId={7} task={task} existingDepIds={[2]} onClose={vi.fn()}/>);
    view.rerender(<TaskModal open teamId={7} task={task} existingDepIds={[2]} onClose={vi.fn()}/>);

    await waitFor(() => {
      expect(screen.getByRole('tab', {name: 'Основное'}).getAttribute('aria-selected')).toBe('true');
    });
  });

  it('keeps dependency selection through search and tabs and submits one payload', async () => {
    renderModal([]);

    fireEvent.click(screen.getByRole('tab', {name: 'Зависимости (0)'}));
    fireEvent.click(screen.getByRole('checkbox', {name: /Зависимость Бета/}));
    fireEvent.change(screen.getByPlaceholderText('Поиск...'), {target: {value: 'Бета'}});
    fireEvent.click(screen.getByRole('tab', {name: 'Основное'}));
    fireEvent.change(screen.getByRole('textbox', {name: 'Имя'}), {target: {value: 'Обновлённая работа'}});
    fireEvent.click(screen.getByRole('tab', {name: 'Зависимости (1)'}));
    expect((screen.getByRole('checkbox', {name: /Зависимость Бета/}) as HTMLInputElement).checked).toBe(true);

    fireEvent.click(screen.getByRole('button', {name: 'Обновить'}));

    await waitFor(() => {
      expect(mocks.save).toHaveBeenCalledWith({
        task_id: 1,
        team_id: 7,
        name: 'Обновлённая работа',
        description: 'Подробное описание',
        instruction_url: 'https://example.test/instruction',
        criticality: 'medium',
        psi_status: 'not_required',
        segment_id: 10,
        completion_template_id: 20,
        dependency_ids: [3],
      });
    });
  });

  it('rejects an invalid instruction URL before save', async () => {
    renderModal([]);

    fireEvent.change(screen.getByRole('textbox', {name: 'Ссылка на инструкцию'}), {
      target: {value: 'javascript:alert(1)'},
    });
    fireEvent.click(screen.getByRole('button', {name: 'Обновить'}));

    expect(await screen.findByText('Укажите полную HTTP(S)-ссылку')).not.toBeNull();
    expect(mocks.save).not.toHaveBeenCalled();
  });

  it.each([
    ['not_required', false, 'not_required'],
    ['not_required', true, 'required'],
    ['required', true, 'required'],
    ['passed', true, 'passed'],
    ['passed', false, 'not_required'],
  ] as const)(
    'maps initial PSI status %s with checkbox %s to %s',
    async (initialStatus, checked, expectedStatus) => {
      renderModal([], {...task, psi_status: initialStatus});

      const checkbox = screen.getByRole('checkbox', {name: 'Требуется ПСИ'}) as HTMLInputElement;
      if (checkbox.checked !== checked) fireEvent.click(checkbox);
      fireEvent.click(screen.getByRole('button', {name: 'Обновить'}));

      await waitFor(() => {
        expect(mocks.save).toHaveBeenCalledWith(expect.objectContaining({psi_status: expectedStatus}));
      });
    },
  );

  it.each(['not_required', 'required', 'passed'] as const)(
    'locks the PSI checkbox and preserves %s when the task has assignments',
    async (initialStatus) => {
      renderModal([], {...task, psi_status: initialStatus, has_assignments: true, has_active_assignments: true});

      const checkbox = screen.getByRole('checkbox', {name: 'Требуется ПСИ'}) as HTMLInputElement;
      expect(checkbox.disabled).toBe(true);
      expect(checkbox.checked).toBe(initialStatus !== 'not_required');
      fireEvent.click(checkbox);
      fireEvent.click(screen.getByRole('button', {name: 'Обновить'}));

      await waitFor(() => {
        expect(mocks.save).toHaveBeenCalledWith(expect.objectContaining({psi_status: initialStatus}));
      });
    },
  );

  it('allows changing the PSI requirement when all assignments are new', async () => {
    renderModal([], {...task, has_assignments: true, has_active_assignments: false});

    const checkbox = screen.getByRole('checkbox', {name: 'Требуется ПСИ'}) as HTMLInputElement;
    expect(checkbox.disabled).toBe(false);
    fireEvent.click(checkbox);
    fireEvent.click(screen.getByRole('button', {name: 'Обновить'}));

    await waitFor(() => {
      expect(mocks.save).toHaveBeenCalledWith(expect.objectContaining({psi_status: 'required'}));
    });
  });

  it('shows separate safe links for the instruction and a URL inside the description', () => {
    render(
      <TaskModal
        open
        teamId={7}
        task={{
          ...task,
          task_status: 'done',
          description: 'Детали: https://example.test/description-link',
          instruction_url: 'https://example.test/instruction-link',
        }}
        existingDepIds={[]}
        onClose={vi.fn()}
      />,
    );

    const instructionLink = screen.getByRole('link', {name: 'https://example.test/instruction-link'});
    expect(instructionLink.getAttribute('target')).toBe('_blank');
    expect(instructionLink.getAttribute('rel')).toContain('noopener');
    expect(instructionLink.getAttribute('rel')).toContain('noreferrer');

    const descriptionLink = screen.getByRole('link', {name: 'https://example.test/description-link'});
    expect(descriptionLink.getAttribute('target')).toBe('_blank');
    expect(descriptionLink.getAttribute('rel')).toContain('noreferrer');
    expect(screen.getByText('Назначений нет')).not.toBeNull();
    expect(mocks.timeline).toHaveBeenCalledWith(task.id, true);
  });
});
