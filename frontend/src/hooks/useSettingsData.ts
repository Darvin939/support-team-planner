import {useQuery} from '@tanstack/react-query';
import {apiGet, buildApiUrl} from '../lib/apiMutate';
import {queryKeys} from '../lib/queryKeys';

export interface User {
  id: number;
  last_name: string | null;
  first_name: string;
  middle_name: string | null;
  role: string;
  login: string | null;
  is_assignee: boolean;
  is_protected: boolean;
  team_ids: number[];
}

export interface Block {
  id: number;
  name: string;
}

export interface BlockTemplateEntry {
  id: number;
  name: string;
  shift_days: number;
}

export interface BlockTemplate {
  id: number;
  name: string;
  segment_id: number;
  blocks: BlockTemplateEntry[];
}

export interface Segment {
  id: number;
  name: string;
}

export function useUsers() {
  return useQuery<User[]>({queryKey: queryKeys.users.all, queryFn: () => apiGet('/api/users')});
}

export function useTeamAssignees(teamId: number) {
  return useQuery<User[]>({
    queryKey: queryKeys.users.assignees(teamId),
    queryFn: () => apiGet(`/api/teams/${teamId}/assignees`),
    enabled: teamId > 0,
  });
}

export interface PaginatedUsersResponse {
  users: User[];
  total: number;
}

export function usePaginatedUsers(offset: number, limit: number, search: string) {
  return useQuery<PaginatedUsersResponse>({
    queryKey: queryKeys.users.paginated(offset, limit, search),
    queryFn: () => apiGet(buildApiUrl('/api/users', {offset, limit, search})),
  });
}

export function useBlocks() {
  return useQuery<Block[]>({queryKey: queryKeys.blocks, queryFn: () => apiGet('/api/blocks')});
}

export function useBlockTemplates() {
  return useQuery<BlockTemplate[]>({queryKey: queryKeys.blockTemplates, queryFn: () => apiGet('/api/block-templates')});
}

export function useFreezeDays() {
  return useQuery<string[]>({queryKey: queryKeys.freezeDays, queryFn: () => apiGet('/api/freeze-days')});
}

export function useSegments() {
  return useQuery<Segment[]>({queryKey: queryKeys.segments, queryFn: () => apiGet('/api/segments')});
}
