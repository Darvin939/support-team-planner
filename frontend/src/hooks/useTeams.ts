import {useQuery} from '@tanstack/react-query';

export interface Team {
  id: number;
  name: string;
  templates?: { id: number; name: string }[];
}

export function useTeams() {
  return useQuery<Team[]>({
    queryKey: ['teams'],
    queryFn: async () => {
      const r = await fetch('/api/teams', { credentials: 'same-origin' });
      if (!r.ok) throw new Error(`GET /api/teams -> ${r.status}`);
      return r.json();
    },
  });
}
