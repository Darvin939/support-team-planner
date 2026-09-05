import {queryOptions, useQuery} from '@tanstack/react-query';
import {apiGet} from '../lib/apiMutate';
import {queryKeys} from '../lib/queryKeys';

export interface Me {
  user_id: number;
  login?: string | null;
  role: string;
  last_name: string | null;
  first_name: string;
  middle_name: string | null;
}

export const ME_STALE_TIME = 60_000;

export const meQueryOptions = queryOptions<Me>({
  queryKey: queryKeys.me,
  queryFn: () => apiGet('/api/me'),
  retry: false,
  staleTime: ME_STALE_TIME,
});

export function useMe() {
  return useQuery(meQueryOptions);
}
