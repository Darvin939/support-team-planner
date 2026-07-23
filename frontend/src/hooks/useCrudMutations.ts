import {message} from 'antd';
import {useMutation, useQueryClient} from '@tanstack/react-query';
import {apiMutate} from '../lib/apiMutate';
import {invalidateSettingsData} from '../lib/queryInvalidation';

/** Shared save (create/update)+delete mutation pair for a Settings-tab entity-with-id modal
 * (`TEntity | 'new' | null` state): POST when the modal entity is `'new'`, PUT otherwise, DELETE
 * by id — with the same invalidate+toast/error shape every migrated tab already used inline. */
export function useCrudMutations<TEntity extends { id: number }, TValues>({
                                                                            queryKey,
                                                                            baseUrl,
                                                                            modalEntity,
                                                                            onSaveSuccess,
                                                                            deleteSuccessMessage,
                                                                          }: {
  queryKey: readonly unknown[];
  baseUrl: string;
  modalEntity: TEntity | 'new' | null;
  onSaveSuccess: () => void;
  /** Shown via message.success on successful delete; omit for tabs that show no delete toast. */
  deleteSuccessMessage?: string;
}) {
  const queryClient = useQueryClient();

  const saveMutation = useMutation({
    mutationFn: (values: TValues) => {
      const isNew = modalEntity === 'new';
      const url = isNew ? baseUrl : `${baseUrl}/${(modalEntity as TEntity).id}`;
      return apiMutate(url, isNew ? 'POST' : 'PUT', values);
    },
    onSuccess: () => {
      invalidateSettingsData(queryClient, queryKey);
      message.success('Сохранено');
      onSaveSuccess();
    },
    onError: (e: Error) => message.error(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => apiMutate(`${baseUrl}/${id}`, 'DELETE'),
    onSuccess: () => {
      invalidateSettingsData(queryClient, queryKey);
      if (deleteSuccessMessage) message.success(deleteSuccessMessage);
    },
    onError: (e: Error) => message.error(e.message),
  });

  return {saveMutation, deleteMutation};
}
