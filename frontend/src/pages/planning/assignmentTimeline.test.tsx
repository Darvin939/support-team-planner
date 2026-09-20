// @vitest-environment jsdom

import {cleanup, render, screen} from '@testing-library/react';
import {afterEach, describe, expect, it} from 'vitest';
import {AssignmentTimeline} from './assignmentTimeline';
import {buildAssignmentTimelineDates, splitAssignmentBlocks} from './assignmentTimelineUtils';

afterEach(cleanup);

describe('assignment timeline helpers', () => {
  it('builds an inclusive date range and splits block names', () => {
    expect(buildAssignmentTimelineDates([{date: '2026-09-03'}, {date: '2026-09-01'}]))
      .toEqual(['2026-09-01', '2026-09-02', '2026-09-03']);
    expect(splitAssignmentBlocks(' Анализ, , Проверка ')).toEqual(['Анализ', 'Проверка']);
  });

  it('renders one status group per date with comma-separated blocks', () => {
    render(<AssignmentTimeline assignments={[
      {date: '2026-09-01', block: 'Анализ, Проверка', status: 'success'},
      {date: '2026-09-03', block: 'Отчёт', status: 'planned'},
    ]}/>);

    expect(screen.getByText('Анализ, Проверка')).toBeTruthy();
    expect(screen.getByText('Отчёт')).toBeTruthy();
    expect(screen.getByText('Успешно')).toBeTruthy();
    expect(screen.getByText('Запланировано')).toBeTruthy();
    expect(screen.getByText('Блок')).toBeTruthy();
    expect(screen.getAllByText('02.09').length).toBeGreaterThan(0);
    expect(screen.queryByText('Комментарий')).toBeNull();
  });

  it('renders empty and error states', () => {
    const {rerender} = render(<AssignmentTimeline assignments={[]}/>);
    expect(screen.getByText('Назначений нет')).toBeTruthy();
    rerender(<AssignmentTimeline assignments={undefined} error/>);
    expect(screen.getByText('Не удалось загрузить назначения')).toBeTruthy();
  });
});
