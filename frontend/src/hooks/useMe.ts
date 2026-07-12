import {useQuery} from '@tanstack/react-query';
import {apiGet} from '../lib/apiMutate';

export interface Me {
  user_id: number;
  role: string;
  last_name: string | null;
  first_name: string;
  middle_name: string | null;
}

export function useMe() {
  return useQuery<Me>({
    queryKey: ['me'],
    queryFn: () => apiGet('/api/me'),
    retry: false,
  });
}
