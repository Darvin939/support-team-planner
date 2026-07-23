import {useQuery} from '@tanstack/react-query';
import {apiGet, buildApiUrl} from '../lib/apiMutate';
import {queryKeys} from '../lib/queryKeys';
import type {Team} from '../domain/types';
export type {Team} from '../domain/types';

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
  return useQuery<PaginatedTeamsResponse>({
    queryKey: queryKeys.paginatedTeams(offset, limit, search),
    queryFn: () => apiGet(buildApiUrl('/api/teams', {offset, limit, search})),
  });
}
