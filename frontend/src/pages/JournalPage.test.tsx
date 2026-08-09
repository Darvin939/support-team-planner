import {describe, expect, it} from 'vitest';
import {buildJournalColumns, buildTaskHistoryColumns} from './JournalPage';


describe('journal table columns', () => {
  it('keeps the server-ordered journal presentation unsortable', () => {
    const columns = buildJournalColumns((id) => id);

    expect(columns.map((column) => column.title)).toEqual([
      'Дата и время', 'Работа', 'Объект', 'Изменение', 'Автор',
    ]);
    expect(columns.every((column) => column.sorter === undefined)).toBe(true);
  });

  it('hides only the redundant entity column below desktop width', () => {
    const columns = buildJournalColumns((id) => id);
    const responsiveColumns = columns.filter((column) => column.responsive !== undefined);

    expect(responsiveColumns).toHaveLength(1);
    expect(responsiveColumns[0].title).toBe('Объект');
    expect(responsiveColumns[0].responsive).toEqual(['lg']);
  });
});

describe('task history modal columns', () => {
  it('matches the compact archive-style table structure', () => {
    const columns = buildTaskHistoryColumns((id) => id);

    expect(columns.map((column) => column.title)).toEqual(['Дата и время', 'Изменение', 'Автор']);
    expect(columns.every((column) => column.sorter === undefined)).toBe(true);
  });
});
