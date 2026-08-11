// @vitest-environment jsdom

import {afterEach, beforeAll, describe, expect, it, vi} from 'vitest';
import {cleanup, fireEvent, render, screen} from '@testing-library/react';
import {TaskCompletionSuggestionModal} from './TaskCompletionSuggestionModal';


beforeAll(() => {
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

afterEach(cleanup);

describe('TaskCompletionSuggestionModal', () => {
  const suggestion = {task_id: 42, task_name: 'Релиз'};

  it('does not render a dialog without a suggestion', () => {
    render(<TaskCompletionSuggestionModal suggestion={null} onConfirm={vi.fn()} onCancel={vi.fn()}/>);
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('shows the task and confirms its standard completion transition', () => {
    const onConfirm = vi.fn();
    render(
      <TaskCompletionSuggestionModal suggestion={suggestion} onConfirm={onConfirm} onCancel={vi.fn()}/>,
    );

    expect(screen.getByText(/Перевести работу «Релиз»/)).not.toBeNull();
    fireEvent.click(screen.getByRole('button', {name: 'Перевести в Выполнена'}));
    expect(onConfirm).toHaveBeenCalledWith(42);
  });

  it('leaves the task unchanged when cancelled', () => {
    const onCancel = vi.fn();
    const onConfirm = vi.fn();
    render(
      <TaskCompletionSuggestionModal suggestion={suggestion} onConfirm={onConfirm} onCancel={onCancel}/>,
    );

    fireEvent.click(screen.getByRole('button', {name: 'Оставить без изменений'}));
    expect(onCancel).toHaveBeenCalledOnce();
    expect(onConfirm).not.toHaveBeenCalled();
  });
});
