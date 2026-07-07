import {useQuery} from '@tanstack/react-query';

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
    queryFn: async () => {
      const r = await fetch('/api/me', { credentials: 'same-origin' });
      if (!r.ok) throw new Error(`GET /api/me -> ${r.status}`);
      return r.json();
    },
    retry: false,
  });
}
