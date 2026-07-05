import {useQuery} from '@tanstack/react-query';

export interface Employee {
  id: number;
  last_name: string;
  first_name: string;
  middle_name: string | null;
}

function formatDisplayName(e: Employee): string {
  if (!e.first_name) return e.last_name;
  const initials = `${e.first_name.charAt(0)}.${e.middle_name ? e.middle_name.charAt(0) + '.' : ''}`;
  return `${e.last_name} ${initials}`;
}

function useEmployeesQuery() {
  return useQuery<Employee[]>({
    queryKey: ['employees'],
    queryFn: async () => {
      const r = await fetch('/api/employees', { credentials: 'same-origin' });
      if (!r.ok) throw new Error(`GET /api/employees -> ${r.status}`);
      return r.json();
    },
    staleTime: 5 * 60 * 1000,
  });
}

/** Кэш имён сотрудников по id — для отображения "Исполнитель" в истории изменений. */
export function useEmployeeNames() {
  const { data } = useEmployeesQuery();
  const byId = new Map(data?.map((e) => [String(e.id), formatDisplayName(e)]));

  return (employeeId: string | null): string => {
    if (!employeeId) return '—';
    return byId.get(employeeId) ?? `#${employeeId}`;
  };
}

/** Список сотрудников с отображаемым именем — для фильтров/пикеров (использует тот же кэш `['employees']`). */
export function useEmployeeOptions(): { value: number; label: string }[] {
  const { data } = useEmployeesQuery();
  return data?.map((e) => ({ value: e.id, label: formatDisplayName(e) })) ?? [];
}
