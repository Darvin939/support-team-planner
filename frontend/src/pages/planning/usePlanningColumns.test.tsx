// @vitest-environment jsdom

import {cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {afterEach, beforeAll, describe, expect, it, vi} from 'vitest';
import type {ReactNode} from 'react';
import {App as AntApp} from 'antd';
import type {Task} from '../../domain/types';
import {TaskNameWithCriticality} from './TaskNameWithCriticality';
import {usePlanningColumns} from './usePlanningColumns';

beforeAll(() => {
  vi.stubGlobal('ResizeObserver', class {
    observe() {}
    unobserve() {}
    disconnect() {}
  });
  vi.stubGlobal('matchMedia', vi.fn().mockImplementation(() => ({
    matches: false,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })));
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('TaskNameWithCriticality', () => {
  it('keeps the criticality badge in the same inline flow as a wrapping task name', () => {
    const name = 'Очень длинное название работы, которое переносится на несколько строк';
    render(<TaskNameWithCriticality name={name} criticality="high"/>);

    const title = screen.getByText(name);
    const criticality = title.querySelector<HTMLElement>('[data-task-row-criticality]');

    expect(criticality).not.toBeNull();
    expect(criticality?.parentElement).toBe(title);
    expect(criticality?.style.display).toBe('inline-block');
    expect(criticality?.style.whiteSpace).toBe('nowrap');
    expect(title.style.display).toBe('');
    expect(screen.getByText('В')).toBeTruthy();
  });
});

const planningTask: Task = {
  id: 12,
  name: 'Работа с ПСИ',
  description: null,
  instruction_url: null,
  criticality: 'medium',
  task_status: 'new',
  psi_status: 'required',
  segment_id: 1,
  segment_name: 'Основной',
  completed_at: null,
  has_active_assignments: false,
  has_assignments: false,
};

function PlanningTaskCell({
  task,
  psiMutate,
}: {
  task: Task;
  psiMutate: (vars: {taskId: number; psiStatus: 'required' | 'passed'}) => void;
}) {
  const columns = usePlanningColumns({
    teamId: 1,
    dates: [],
    assignmentByKey: new Map(),
    depsByTask: new Map(),
    today: '2026-08-22',
    token: {} as never,
    freezeDays: new Set(),
    isUser: true,
    chipDragSuppressRef: {current: false},
    panSuppressRef: {current: false},
    selectSuppressRef: {current: false},
    selectedAssignmentIds: new Set(),
    onToggleAssignment: vi.fn(),
    onClearSelection: vi.fn(),
    priorityMutation: {mutate: vi.fn()},
    statusMutation: {mutate: vi.fn()},
    psiStatusMutation: {mutate: psiMutate},
    assignmentStatusMutation: {mutate: vi.fn()},
    setGraphModal: vi.fn(),
    setTaskModal: vi.fn(),
    setAssignmentModal: vi.fn(),
    onDepNavigate: vi.fn(),
  });
  const renderCell = columns[0].render as (_: unknown, task: Task, index: number) => ReactNode;
  return <>{renderCell(undefined, task, 0)}</>;
}

describe('usePlanningColumns PSI context action', () => {
  it('confirms required to passed and does nothing when confirmation is cancelled', async () => {
    const mutate = vi.fn();
    render(<AntApp><PlanningTaskCell task={planningTask} psiMutate={mutate}/></AntApp>);

    fireEvent.contextMenu(screen.getByText(planningTask.name));
    fireEvent.click(await screen.findByText('ПСИ пройдено'));
    expect(await screen.findByRole('dialog', {name: 'Отметить ПСИ пройденным?'})).toBeTruthy();
    expect(mutate).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', {name: 'Отмена'}));
    expect(mutate).not.toHaveBeenCalled();

    cleanup();
    render(<AntApp><PlanningTaskCell task={planningTask} psiMutate={mutate}/></AntApp>);
    fireEvent.contextMenu(screen.getByText(planningTask.name));
    fireEvent.click(await screen.findByText('ПСИ пройдено'));
    fireEvent.click(await screen.findByRole('button', {name: 'Подтвердить'}));
    await waitFor(() => expect(mutate).toHaveBeenCalledWith({taskId: 12, psiStatus: 'passed'}));
  });

  it('confirms passed to required and omits PSI action for not_required', async () => {
    const mutate = vi.fn();
    const view = render(
      <AntApp><PlanningTaskCell task={{...planningTask, psi_status: 'passed'}} psiMutate={mutate}/></AntApp>,
    );

    fireEvent.contextMenu(screen.getByText(planningTask.name));
    fireEvent.click(await screen.findByText('Вернуть статус «Требуется ПСИ»'));
    expect(await screen.findByRole('dialog', {name: 'Вернуть статус «Требуется ПСИ»?'})).toBeTruthy();
    fireEvent.click(screen.getByRole('button', {name: 'Подтвердить'}));
    await waitFor(() => expect(mutate).toHaveBeenCalledWith({taskId: 12, psiStatus: 'required'}));

    view.unmount();
    render(<AntApp><PlanningTaskCell task={{...planningTask, psi_status: 'not_required'}} psiMutate={vi.fn()}/></AntApp>);
    fireEvent.contextMenu(screen.getByText(planningTask.name));
    expect(screen.queryByText('ПСИ пройдено')).toBeNull();
    expect(screen.queryByText('Вернуть статус «Требуется ПСИ»')).toBeNull();
  });
});

describe('usePlanningColumns copy assignments action', () => {
  function setClipboard(writeText = vi.fn().mockResolvedValue(undefined)) {
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: {writeText},
    });
    return writeText;
  }

  function mockHistory(body: unknown, ok = true) {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok,
      status: ok ? 200 : 500,
      json: vi.fn().mockResolvedValue(body),
    }));
  }

  it('is available for a terminal task and copies formatted successful history', async () => {
    const writeText = setClipboard();
    mockHistory([
      {
        id: 1,
        task_id: planningTask.id,
        date: '2026-09-05',
        block: 'GF, GA',
        status: 'success',
        user_id: null,
        user_name: null,
        comment: null,
        time_spent: null,
      },
    ]);
    const terminalTask = {...planningTask, task_status: 'done' as const};
    render(<AntApp><PlanningTaskCell task={terminalTask} psiMutate={vi.fn()}/></AntApp>);

    fireEvent.contextMenu(screen.getByText(terminalTask.name));
    fireEvent.click(await screen.findByText('Копировать успешные назначения'));

    await waitFor(() => expect(writeText).toHaveBeenCalledWith(
      `${terminalTask.name}\nGF, GA - 05.09.2026`,
    ));
    expect(await screen.findByText('Назначения скопированы')).toBeTruthy();
  });

  it('does not touch the clipboard when successful assignments are empty', async () => {
    const writeText = setClipboard();
    mockHistory([]);
    render(<AntApp><PlanningTaskCell task={planningTask} psiMutate={vi.fn()}/></AntApp>);

    fireEvent.contextMenu(screen.getByText(planningTask.name));
    fireEvent.click(await screen.findByText('Копировать успешные назначения'));

    expect(await screen.findByText('Нет успешных назначений')).toBeTruthy();
    expect(writeText).not.toHaveBeenCalled();
  });

  it('shows an error when loading or clipboard writing fails', async () => {
    const writeText = setClipboard();
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network error')));
    const view = render(<AntApp><PlanningTaskCell task={planningTask} psiMutate={vi.fn()}/></AntApp>);

    fireEvent.contextMenu(screen.getByText(planningTask.name));
    fireEvent.click(await screen.findByText('Копировать успешные назначения'));
    expect(await screen.findByText('Не удалось скопировать назначения')).toBeTruthy();
    expect(writeText).not.toHaveBeenCalled();

    view.unmount();
    writeText.mockRejectedValueOnce(new Error('clipboard denied'));
    mockHistory([{
      id: 1,
      task_id: planningTask.id,
      date: '2026-09-05',
      block: 'GF',
      status: 'success',
      user_id: null,
      user_name: null,
      comment: null,
      time_spent: null,
    }]);
    render(<AntApp><PlanningTaskCell task={planningTask} psiMutate={vi.fn()}/></AntApp>);
    fireEvent.contextMenu(screen.getByText(planningTask.name));
    fireEvent.click(await screen.findByText('Копировать успешные назначения'));
    await waitFor(() => expect(writeText).toHaveBeenCalled());
    expect(await screen.findByText('Не удалось скопировать назначения')).toBeTruthy();
  });
});
