// @vitest-environment jsdom
import {act, cleanup, renderHook, waitFor} from '@testing-library/react';
import {afterEach, describe, expect, it, vi} from 'vitest';
import {useTaskCompletionSuggestions} from './useTaskCompletionSuggestions';

const query = vi.hoisted(() => ({data: undefined as undefined | {completion_ready: boolean},
  isFetching: false, isError: false}));
vi.mock('../../hooks/usePlanningData', () => ({useTaskById: () => query}));
afterEach(() => {cleanup(); query.data = undefined; query.isFetching = false; query.isError = false;});
const first = {task_id: 1, task_name: 'First'};
const second = {task_id: 2, task_name: 'Second'};

describe('completion suggestions', () => {
  it('does not open on loading ready data and keeps dismissed suggestions closed on refetch', () => {
    query.data = {completion_ready: true};
    const {result, rerender} = renderHook(() => useTaskCompletionSuggestions(1, true));
    expect(result.current.suggestion).toBeNull();
    act(() => result.current.receive({task_completion_suggestion: first}));
    expect(result.current.suggestion).toEqual(first);
    act(() => result.current.dismiss());
    rerender();
    expect(result.current.suggestion).toBeNull();
    act(() => result.current.enqueue(first));
    expect(result.current.suggestion).toEqual(first);
    query.isFetching = true;
    rerender();
    expect(result.current.suggestion).toEqual(first);
  });

  it('queues every bulk suggestion once and waits for current readiness', () => {
    query.isFetching = true;
    const {result, rerender} = renderHook(() => useTaskCompletionSuggestions(1, true));
    act(() => result.current.receive({task_completion_suggestion: first,
      task_completion_suggestions: [first, second, first]}));
    expect(result.current.suggestion).toBeNull();
    query.data = {completion_ready: true}; query.isFetching = false;
    rerender();
    expect(result.current.suggestion).toEqual(first);
    act(() => result.current.dismiss());
    expect(result.current.suggestion).toEqual(second);
    act(() => result.current.dismiss());
    expect(result.current.suggestion).toBeNull();
  });

  it('removes obsolete suggestions and allows a later restored readiness', async () => {
    query.data = {completion_ready: true};
    const {result, rerender} = renderHook(() => useTaskCompletionSuggestions(1, true));
    act(() => result.current.enqueue(first));
    query.data = {completion_ready: false}; rerender();
    await waitFor(() => expect(result.current.suggestion).toBeNull());
    query.data = {completion_ready: true}; rerender();
    expect(result.current.suggestion).toBeNull();
    act(() => result.current.enqueue(first));
    expect(result.current.suggestion).toEqual(first);
  });

  it('hides suggestions for readers and clears them when changing team', () => {
    query.data = {completion_ready: true};
    const {result, rerender} = renderHook(({team, allowed}) => useTaskCompletionSuggestions(team, allowed),
      {initialProps: {team: 1, allowed: false}});
    act(() => result.current.receive({task_completion_suggestion: first}));
    expect(result.current.suggestion).toBeNull();
    rerender({team: 1, allowed: true});
    act(() => result.current.enqueue(first));
    expect(result.current.suggestion).toEqual(first);
    rerender({team: 2, allowed: true});
    expect(result.current.suggestion).toBeNull();
  });
});
