// @vitest-environment jsdom

import {afterEach, beforeAll, describe, expect, it, vi} from 'vitest';
import {cleanup, render, screen} from '@testing-library/react';
import {Form} from 'antd';
import {AssignmentStatusField} from './AssignmentStatusField';
import {assignmentStatusForSave, canChangeAssignmentStatus} from './assignmentStatusRolePolicy';


afterEach(cleanup);

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

describe('assignment status role policy', () => {
  it('does not expose an enabled status control to a user', () => {
    render(
      <Form initialValues={{status: 'new'}}>
        <AssignmentStatusField disabled/>
      </Form>,
    );

    expect((screen.getByRole('combobox', {name: 'Статус'}) as HTMLInputElement).disabled).toBe(true);
  });

  it('keeps status actions for elevated roles only', () => {
    expect(canChangeAssignmentStatus(true)).toBe(false);
    expect(canChangeAssignmentStatus(false)).toBe(true);
  });

  it('forces new in a user create payload and preserves an editor choice', () => {
    expect(assignmentStatusForSave(true, 'planned')).toBe('new');
    expect(assignmentStatusForSave(false, 'planned')).toBe('planned');
  });
});
