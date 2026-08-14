// @vitest-environment jsdom

import {afterEach, beforeAll, describe, expect, it, vi} from 'vitest';
import {cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import type {Task} from '../../domain/types';
import {TaskModal} from './TaskModal';

const mocks = vi.hoisted(() => ({
  save: vi.fn(),
  remove: vi.fn(),
  activeTasks: [
    {
      id: 2,
      name: 'Зависимость Альфа',
      criticality: 'high',
      task_status: 'ready',
    },
    {
      id: 3,
      name: 'Зависимость Бета',
      criticality: 'low',
      task_status: 'new',
    },
  ],
  segments: [{id: 10, name: 'Основной сегмент'}],
}));

vi.mock('../../hooks/usePlanningData', () => ({
  useActiveTasksList: () => ({
    data: mocks.activeTasks,
    isLoading: false,
  }),
}));

vi.mock('../../hooks/useMe', () => ({useMe: () => ({data: {role: 'admin'}})}));
vi.mock('../../hooks/useSettingsData', () => ({
  useSegments: () => ({data: mocks.segments}),
}));
vi.mock('../../hooks/useDebouncedValue', () => ({useDebouncedValue: (value: string) => value}));
vi.mock('../../hooks/useIsMobile', () => ({useIsMobile: () => false}));
vi.mock('../../hooks/useTaskMutations', () => ({
  useSaveTaskMutation: () => ({mutate: mocks.save, isPending: false}),
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
  completed_at: null,
  has_active_assignments: false,
};

function renderModal(existingDepIds = [2]) {
  return render(
    <TaskModal open teamId={7} task={task} existingDepIds={existingDepIds} onClose={vi.fn()}/>,
  );
}

describe('TaskModal', () => {
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
  });
});
