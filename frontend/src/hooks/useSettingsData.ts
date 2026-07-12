import {useQuery} from '@tanstack/react-query';
import {apiGet} from '../lib/apiMutate';

export interface User {
  id: number;
  last_name: string | null;
  first_name: string;
  middle_name: string | null;
  role: string;
  login: string | null;
  is_assignee: boolean;
  is_protected: boolean;
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
  return useQuery<User[]>({ queryKey: ['users'], queryFn: () => apiGet('/api/users') });
}

export function useBlocks() {
  return useQuery<Block[]>({ queryKey: ['blocks'], queryFn: () => apiGet('/api/blocks') });
}

export function useBlockTemplates() {
  return useQuery<BlockTemplate[]>({ queryKey: ['block-templates'], queryFn: () => apiGet('/api/block-templates') });
}

export function useFreezeDays() {
  return useQuery<string[]>({ queryKey: ['freeze-days'], queryFn: () => apiGet('/api/freeze-days') });
}

export function useSegments() {
  return useQuery<Segment[]>({ queryKey: ['segments'], queryFn: () => apiGet('/api/segments') });
}
