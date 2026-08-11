import {Modal} from 'antd';
import type {ApiResult} from '../../lib/apiMutate';


export type TaskCompletionSuggestion = NonNullable<ApiResult['task_completion_suggestion']>;

export function TaskCompletionSuggestionModal({
  suggestion,
  onConfirm,
  onCancel,
}: {
  suggestion: TaskCompletionSuggestion | null;
  onConfirm: (taskId: number) => void;
  onCancel: () => void;
}) {
  return (
    <Modal
      title="Все назначения шаблона выполнены"
      open={suggestion !== null}
      okText="Перевести в Выполнена"
      cancelText="Оставить без изменений"
      onOk={() => suggestion && onConfirm(suggestion.task_id)}
      onCancel={onCancel}
    >
      {suggestion && (
        <p>Перевести работу «{suggestion.task_name}» в статус «Выполнена»?</p>
      )}
    </Modal>
  );
}
