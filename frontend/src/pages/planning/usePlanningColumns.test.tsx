// @vitest-environment jsdom

import {cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {afterEach, beforeAll, describe, expect, it, vi} from 'vitest';
import type {ReactNode} from 'react';
import {Modal} from 'antd';
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
    const confirm = vi.spyOn(Modal, 'confirm').mockReturnValue({destroy: vi.fn(), update: vi.fn()});
    render(<PlanningTaskCell task={planningTask} psiMutate={mutate}/>);

    fireEvent.contextMenu(screen.getByText(planningTask.name));
    fireEvent.click(await screen.findByText('Отметить ПСИ пройденным'));
    expect(confirm).toHaveBeenCalledWith(expect.objectContaining({title: 'Отметить ПСИ пройденным?'}));
    expect(mutate).not.toHaveBeenCalled();

    const config = confirm.mock.calls[0][0];
    await config.onOk?.();
    await waitFor(() => expect(mutate).toHaveBeenCalledWith({taskId: 12, psiStatus: 'passed'}));
  });

  it('confirms passed to required and omits PSI action for not_required', async () => {
    const mutate = vi.fn();
    const confirm = vi.spyOn(Modal, 'confirm').mockReturnValue({destroy: vi.fn(), update: vi.fn()});
    const view = render(
      <PlanningTaskCell task={{...planningTask, psi_status: 'passed'}} psiMutate={mutate}/>,
    );

    fireEvent.contextMenu(screen.getByText(planningTask.name));
    fireEvent.click(await screen.findByText('Вернуть статус «Требуется ПСИ»'));
    expect(confirm).toHaveBeenCalledWith(expect.objectContaining({title: 'Вернуть статус «Требуется ПСИ»?'}));
    await confirm.mock.calls[0][0].onOk?.();
    await waitFor(() => expect(mutate).toHaveBeenCalledWith({taskId: 12, psiStatus: 'required'}));

    view.unmount();
    render(<PlanningTaskCell task={{...planningTask, psi_status: 'not_required'}} psiMutate={vi.fn()}/>);
    fireEvent.contextMenu(screen.getByText(planningTask.name));
    expect(screen.queryByText('Отметить ПСИ пройденным')).toBeNull();
    expect(screen.queryByText('Вернуть статус «Требуется ПСИ»')).toBeNull();
  });
});
