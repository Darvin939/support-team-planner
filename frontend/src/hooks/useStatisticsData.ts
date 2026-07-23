import {useQuery} from '@tanstack/react-query';
import {apiGet, buildApiUrl} from '../lib/apiMutate';
import {queryKeys} from '../lib/queryKeys';

export interface ActiveAssignment {
  id: number;
  task_name: string;
  team_name: string | null;
  criticality: 'high' | 'medium' | 'low';
  date: string;
  block: string | null;
  status: 'new' | 'planned' | 'rollback' | 'success' | 'cancelled';
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

export function useActiveAssignments(from: string, to: string, teamIds: number[], offset: number, limit: number) {
  return useQuery<ActiveAssignmentsResponse>({
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
