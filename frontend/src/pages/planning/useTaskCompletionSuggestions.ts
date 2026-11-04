import {useCallback, useEffect, useState} from 'react';
import {useTaskById} from '../../hooks/usePlanningData';
import type {ApiResult} from '../../lib/apiMutate';
import type {TaskCompletionSuggestion} from './TaskCompletionSuggestionModal';

export function useTaskCompletionSuggestions(teamId: number | undefined, enabled: boolean) {
  const [queue, setQueue] = useState<TaskCompletionSuggestion[]>([]);
  const head = queue[0];
  const taskQuery = useTaskById(teamId ?? 0, enabled ? head?.task_id ?? null : null);
  const dismiss = useCallback(() => setQueue((items) => items.slice(1)), []);
  const enqueue = useCallback((suggestion: TaskCompletionSuggestion) => {
    if (!enabled) return;
    setQueue((items) => items.some((item) => item.task_id === suggestion.task_id)
      ? items : [...items, suggestion]);
  }, [enabled]);
  const receive = useCallback((result: ApiResult) => {
    const items = result.task_completion_suggestions
      ?? (result.task_completion_suggestion ? [result.task_completion_suggestion] : []);
    items.forEach(enqueue);
  }, [enqueue]);

  useEffect(() => setQueue([]), [teamId, enabled]);
  useEffect(() => {
    if (head && !taskQuery.isFetching && (taskQuery.isError
      || (taskQuery.data && !taskQuery.data.completion_ready))) dismiss();
  }, [head, taskQuery.data, taskQuery.isError, taskQuery.isFetching, dismiss]);

  return {
    suggestion: enabled && head && taskQuery.data?.completion_ready ? head : null,
    enqueue,
    receive,
    dismiss,
  };
}
