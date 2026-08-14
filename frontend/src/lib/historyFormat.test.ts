import {describe, expect, it} from 'vitest';
import {formatHistoryValue} from './historyFormat';

const getUserName = (id: string) => `user-${id}`;

describe('formatHistoryValue enum labels', () => {
  it('formats current task statuses and preserves unknown values', () => {
    expect(formatHistoryValue('task_status', 'new', getUserName)).toBe('Новый');
    expect(formatHistoryValue('task_status', 'legacy', getUserName)).toBe('legacy');
  });

  it('uses centralized PSI labels and preserves unknown values', () => {
    expect(formatHistoryValue('psi_status', 'required', getUserName)).toBe('Требуется ПСИ');
    expect(formatHistoryValue('psi_status', 'legacy', getUserName)).toBe('legacy');
  });
});
