import {useQuery} from '@tanstack/react-query';
import {apiGet, buildApiUrl} from '../lib/apiMutate';
import {queryKeys} from '../lib/queryKeys';
import type {Dayjs} from 'dayjs';
import {API_DATE_FORMAT} from '../lib/dateFormats';

export interface ActiveAssignment {
  id: number;
  task_name: string;
  team_name: string | null;
  criticality: 'high' | 'medium' | 'low';
  date: string;
  block: string | null;
  status: 'new' | 'planned' | 'rollback' | 'success' | 'unsuccessful' | 'cancelled';
  user_name: string | null;
  comment: string | null;
}

export interface ActiveAssignmentsResponse {
  items: ActiveAssignment[];
  total: number;
  stats: {
    status: {new: number; planned: number};
    criticality: {high: number; medium: number; low: number};
  };
}

export interface ActiveAssignmentDateCount {
  date: string;
  count: number;
}

export function getStatisticsCalendarRange(month: Dayjs): {from: string; to: string} {
  return {
    from: month.startOf('month').format(API_DATE_FORMAT),
    to: month.endOf('month').format(API_DATE_FORMAT),
  };
}

export function useActiveAssignments(from: string, to: string, teamIds: number[], offset: number, limit: number, enabled = true) {
  return useQuery<ActiveAssignmentsResponse>({
    enabled,
    queryKey: queryKeys.assignments.activeList(from, to, teamIds, offset, limit),
    queryFn: () => apiGet(buildApiUrl('/api/active-assignments/0', {
      start_date: from,
      end_date: to,
      team_ids: teamIds.join(','),
      offset,
      limit,
    })),
  });
}

export function useActiveAssignmentDateCounts(from: string, to: string, teamIds: number[], enabled = true) {
  return useQuery<ActiveAssignmentDateCount[]>({
    enabled,
    queryKey: queryKeys.assignments.dateCounts(from, to, teamIds),
    queryFn: () => apiGet(buildApiUrl('/api/active-assignment-counts/0', {
      start_date: from,
      end_date: to,
      team_ids: teamIds.join(','),
    })),
  });
}
