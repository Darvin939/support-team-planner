import {useEffect, useState} from 'react';

export function usePlanningSelection(reset: {
  teamId: number | undefined;
  search: string;
  showCompleted: boolean;
  page: number;
  pageSize: number;
}) {
  const [selectedAssignmentIds, setSelectedAssignmentIds] = useState<Set<number>>(new Set());

  useEffect(() => {
    setSelectedAssignmentIds(new Set());
  }, [reset.teamId, reset.search, reset.showCompleted, reset.page, reset.pageSize]);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setSelectedAssignmentIds((current) => current.size > 0 ? new Set() : current);
      }
    }
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  return {selectedAssignmentIds, setSelectedAssignmentIds};
}
