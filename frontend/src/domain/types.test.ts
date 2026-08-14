import {describe, expect, it} from 'vitest';
import taskTransitions from '../data/taskTransitions.json';
import {
  ASSIGNMENT_STATUS_LABELS,
  ASSIGNMENT_STATUS_OPTIONS,
  CRITICALITY_LABELS,
  CRITICALITY_OPTIONS,
  PSI_STATUS_LABELS,
  PSI_STATUS_OPTIONS,
  ROLE_OPTIONS,
  TASK_STATUS_LABELS,
  TASK_STATUS_OPTIONS,
} from './types';

describe('domain enum contracts', () => {
  it('contains only current task statuses in active options and transitions', () => {
    const statuses = TASK_STATUS_OPTIONS.map(({value}) => value);
    expect(statuses).toEqual(['new', 'done', 'cancelled']);
    expect(new Set([...Object.keys(taskTransitions), ...Object.values(taskTransitions).flat()])).toEqual(
      new Set(statuses),
    );
  });

  it('keeps options and labels aligned for current enums', () => {
    expect(ASSIGNMENT_STATUS_OPTIONS.map(({value}) => value)).toEqual(Object.keys(ASSIGNMENT_STATUS_LABELS));
    expect(CRITICALITY_OPTIONS.map(({value}) => value).sort()).toEqual(Object.keys(CRITICALITY_LABELS).sort());
    expect(PSI_STATUS_OPTIONS.map(({value}) => value)).toEqual(Object.keys(PSI_STATUS_LABELS));
    expect(ROLE_OPTIONS.map(({value}) => value)).toEqual(['user', 'editor', 'admin']);
    expect(TASK_STATUS_OPTIONS.map(({value}) => value)).toEqual(Object.keys(TASK_STATUS_LABELS));
  });

  it('does not expose legacy task labels', () => {
    expect(Object.keys(TASK_STATUS_LABELS)).not.toContain('ready');
    expect(Object.keys(TASK_STATUS_LABELS)).not.toContain('in_progress');
  });
});
