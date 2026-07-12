import {useQuery} from '@tanstack/react-query';
import {apiGet} from '../lib/apiMutate';

export interface User {
  id: number;
  last_name: string | null;
  first_name: string;
  middle_name: string | null;
}

export function formatDisplayName(u: Pick<User, 'last_name' | 'first_name' | 'middle_name'>): string {
  if (!u.last_name) return u.first_name;
  if (!u.first_name) return u.last_name;
  const initials = `${u.first_name.charAt(0)}.${u.middle_name ? u.middle_name.charAt(0) + '.' : ''}`;
  return `${u.last_name} ${initials}`;
}

function useUsersQuery() {
  return useQuery<User[]>({
    queryKey: ['users'],
    queryFn: () => apiGet('/api/users'),
    staleTime: 5 * 60 * 1000,
  });
}

/** Кэш имён пользователей по id — для отображения "Исполнитель" в истории изменений. */
export function useUserNames() {
  const { data } = useUsersQuery();
  const byId = new Map(data?.map((u) => [String(u.id), formatDisplayName(u)]));

  return (userId: string | null): string => {
    if (!userId) return '—';
    return byId.get(userId) ?? `#${userId}`;
  };
}

/** Список пользователей с отображаемым именем — для фильтров/пикеров (использует тот же кэш `['users']`). */
export function useUserOptions(): { value: number; label: string }[] {
  const { data } = useUsersQuery();
  return data?.map((u) => ({ value: u.id, label: formatDisplayName(u) })) ?? [];
}
