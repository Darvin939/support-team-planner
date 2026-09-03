import {describe, expect, it} from 'vitest';
import type {Assignment, Task} from '../../domain/types';
import {isAssignmentDragLocked, isPsiPlanningBlocked} from './psiAssignmentPolicy';

const task = {
  id: 1,
  task_status: 'new',
  psi_status: 'required',
} as Task;
const assignment = {task_id: 1, status: 'new'} as Assignment;

describe('PSI assignment policy', () => {
  it('allows empty cells and new assignments while PSI is required', () => {
    expect(isPsiPlanningBlocked('required', null)).toBe(false);
    expect(isPsiPlanningBlocked('required', 'new')).toBe(false);
    expect(isAssignmentDragLocked(task, assignment)).toBe(false);
  });

  it('blocks planning and dragging non-new assignments while PSI is required', () => {
    expect(isPsiPlanningBlocked('required', 'planned')).toBe(true);
    expect(isPsiPlanningBlocked('required', 'success')).toBe(true);
    expect(isAssignmentDragLocked(task, {...assignment, status: 'planned'})).toBe(true);
  });

  it('preserves terminal locking and allows normal active planning after PSI', () => {
    expect(isAssignmentDragLocked({...task, task_status: 'done'}, assignment)).toBe(true);
    expect(isAssignmentDragLocked({...task, psi_status: 'passed'}, {...assignment, status: 'planned'})).toBe(false);
  });
});
