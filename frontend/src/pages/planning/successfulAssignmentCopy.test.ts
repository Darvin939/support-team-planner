import {describe, expect, it} from 'vitest';
import type {Assignment, AssignmentStatus} from '../../domain/types';
import {buildSuccessfulAssignmentsText} from './successfulAssignmentCopy';

function assignment(
  id: number,
  date: string,
  block: string | null,
  status: AssignmentStatus = 'success',
): Assignment {
  return {
    id,
    task_id: 12,
    date,
    block,
    status,
    user_id: null,
    user_name: null,
    comment: null,
    time_spent: null,
  };
}

describe('buildSuccessfulAssignmentsText', () => {
  it('keeps each block only on its latest successful date and sorts date groups', () => {
    expect(buildSuccessfulAssignmentsText('Работа', [
      assignment(1, '2026-09-02', 'GF, GA'),
      assignment(2, '2026-09-01', 'BS'),
      assignment(3, '2026-09-03', 'GF'),
      assignment(4, '2026-09-04', 'GF', 'planned'),
    ])).toBe('Работа\nBS - 01.09.2026\nGA - 02.09.2026\nGF - 03.09.2026');
  });

  it('groups blocks with the same final date and trims composite values', () => {
    expect(buildSuccessfulAssignmentsText('Работа', [
      assignment(1, '2026-09-05', ' GF, , GA '),
      assignment(2, '2026-09-05', 'BS'),
    ])).toBe('Работа\nGF, GA, BS - 05.09.2026');
  });

  it('returns null for empty blocks and non-successful assignments', () => {
    expect(buildSuccessfulAssignmentsText('Работа', [
      assignment(1, '2026-09-05', null),
      assignment(2, '2026-09-06', ' , '),
      assignment(3, '2026-09-07', 'GF', 'cancelled'),
    ])).toBeNull();
  });
});
