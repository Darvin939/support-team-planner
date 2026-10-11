import {useMutation, useQuery, useQueryClient} from '@tanstack/react-query';
import {message} from 'antd';
import {apiGet, apiMutate} from '../lib/apiMutate';
import {queryKeys} from '../lib/queryKeys';

export interface ReleaseNote {
  version: string;
  date: string;
  title: string;
  changes: string[];
}

export interface ReleaseChangeLogData {
  application: {
    release_version: string;
    build_id: string;
  };
  releases: ReleaseNote[];
  unseen_releases: ReleaseNote[];
}

export function useReleaseChangeLog() {
  return useQuery<ReleaseChangeLogData>({
    queryKey: queryKeys.releaseChangeLog,
    queryFn: () => apiGet('/api/release-change-log'),
    staleTime: 60_000,
    refetchOnWindowFocus: true,
    retry: false,
  });
}

export function useMarkReleaseVersionsSeen() {
  const queryClient = useQueryClient();
  return useMutation<{success: boolean; marked: number}, Error, string[]>({
    mutationFn: (releaseVersions) => apiMutate(
      '/api/release-change-log/seen', 'POST', {release_versions: releaseVersions},
    ),
    onSuccess: () => queryClient.invalidateQueries({queryKey: queryKeys.releaseChangeLog}),
    onError: () => message.error('Не удалось отметить релизы просмотренными'),
  });
}
