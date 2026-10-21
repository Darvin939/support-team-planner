// @vitest-environment jsdom

import {act, renderHook} from '@testing-library/react';
import {describe, expect, it} from 'vitest';
import type {Task} from '../../domain/types';
import {usePlanningFilters} from './usePlanningFilters';

const tasks: Task[] = [
  {
    id: 1, name: 'Не требуется', description: null, instruction_url: null, criticality: 'low',
    task_status: 'new', psi_status: 'not_required', segment_id: 1, segment_name: 'A', completed_at: null,
    has_active_assignments: false, has_assignments: false,
  },
  {
    id: 2, name: 'Требуется', description: null, instruction_url: null, criticality: 'low',
    task_status: 'new', psi_status: 'required', segment_id: 1, segment_name: 'A', completed_at: null,
    has_active_assignments: false, has_assignments: false,
  },
  {
    id: 3, name: 'Пройдено', description: null, instruction_url: null, criticality: 'low',
    task_status: 'new', psi_status: 'passed', segment_id: 1, segment_name: 'A', completed_at: null,
    has_active_assignments: false, has_assignments: false,
  },
];

describe('usePlanningFilters PSI status', () => {
  it('keeps every task when no PSI status is selected', () => {
    const {result} = renderHook(() => usePlanningFilters(tasks, new Map()));

    expect(result.current.filteredTasks.map((task) => task.id)).toEqual([1, 2, 3]);
  });

  it('filters tasks by one or multiple selected PSI statuses', () => {
    const {result} = renderHook(() => usePlanningFilters(tasks, new Map()));

    act(() => result.current.setPsiStatuses(['required']));
    expect(result.current.filteredTasks.map((task) => task.id)).toEqual([2]);

    act(() => result.current.setPsiStatuses(['not_required', 'passed']));
    expect(result.current.filteredTasks.map((task) => task.id)).toEqual([1, 3]);
  });

  it('keeps every task after clearing PSI status selection', () => {
    const {result} = renderHook(() => usePlanningFilters(tasks, new Map()));

    act(() => result.current.setPsiStatuses(['passed']));
    act(() => result.current.setPsiStatuses([]));

    expect(result.current.filteredTasks.map((task) => task.id)).toEqual([1, 2, 3]);
  });
});
