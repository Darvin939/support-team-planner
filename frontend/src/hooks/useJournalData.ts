import {useQuery} from '@tanstack/react-query';
import type {HistoryEntry} from '../lib/historyFormat';
import {apiGet, buildApiUrl} from '../lib/apiMutate';
import {queryKeys} from '../lib/queryKeys';

export const JOURNAL_PAGE_SIZE = 20;

export interface JournalItem extends HistoryEntry {
  task_id: number;
}

export interface JournalFilters {
  search: string;
  dateFrom: string | null;
  dateTo: string | null;
  changedByUserId: number | null;
}

export function useJournal(teamId: number | undefined, offset: number, pageSize: number, filters: JournalFilters) {
  return useQuery<{items: JournalItem[]; total: number}>({
    queryKey: queryKeys.journal.list(teamId, offset, pageSize, filters),
    enabled: teamId !== undefined,
    queryFn: () => apiGet(buildApiUrl(`/api/journal/${teamId}`, {
      offset,
      limit: pageSize,
      search: filters.search,
      date_from: filters.dateFrom,
      date_to: filters.dateTo,
      changed_by_user_id: filters.changedByUserId,
    })),
  });
}
