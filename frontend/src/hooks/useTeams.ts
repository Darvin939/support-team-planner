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
