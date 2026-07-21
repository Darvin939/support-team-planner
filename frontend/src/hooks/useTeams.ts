import {useQuery} from '@tanstack/react-query';
import {apiGet} from '../lib/apiMutate';
import {queryKeys} from '../lib/queryKeys';

export interface Team {
  id: number;
  name: string;
  templates?: { id: number; name: string }[];
}

export function useTeams() {
  return useQuery<Team[]>({
    queryKey: queryKeys.teams,
    queryFn: () => apiGet('/api/teams'),
  });
}

export interface PaginatedTeamsResponse {
  teams: Team[];
  total: number;
}

export function usePaginatedTeams(offset: number, limit: number, search: string) {
  const params = new URLSearchParams({offset: String(offset), limit: String(limit)});
  if (search) params.set('search', search);
  return useQuery<PaginatedTeamsResponse>({
    queryKey: queryKeys.paginatedTeams(offset, limit, search),
    queryFn: () => apiGet(`/api/teams?${params}`),
  });
}
