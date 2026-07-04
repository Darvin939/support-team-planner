import {useQuery} from '@tanstack/react-query';

interface Employee {
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

/** Кэш имён сотрудников по id — для отображения "Исполнитель" в истории изменений. */
export function useEmployeeNames() {
  const { data } = useQuery<Employee[]>({
    queryKey: ['employees'],
    queryFn: async () => {
      const r = await fetch('/api/employees', { credentials: 'same-origin' });
      if (!r.ok) throw new Error(`GET /api/employees -> ${r.status}`);
      return r.json();
    },
    staleTime: 5 * 60 * 1000,
  });

  const byId = new Map(data?.map((e) => [String(e.id), formatDisplayName(e)]));

  return (employeeId: string | null): string => {
    if (!employeeId) return '—';
    return byId.get(employeeId) ?? `#${employeeId}`;
  };
}
