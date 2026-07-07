import {useQuery} from '@tanstack/react-query';

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
  blocks: BlockTemplateEntry[];
}

async function getJson<T>(url: string): Promise<T> {
  const r = await fetch(url, { credentials: 'same-origin' });
  if (!r.ok) throw new Error(`GET ${url} -> ${r.status}`);
  return r.json();
}

export function useUsers() {
  return useQuery<User[]>({ queryKey: ['users'], queryFn: () => getJson('/api/users') });
}

export function useBlocks() {
  return useQuery<Block[]>({ queryKey: ['blocks'], queryFn: () => getJson('/api/blocks') });
}

export function useBlockTemplates() {
  return useQuery<BlockTemplate[]>({ queryKey: ['block-templates'], queryFn: () => getJson('/api/block-templates') });
}

export function useFreezeDays() {
  return useQuery<string[]>({ queryKey: ['freeze-days'], queryFn: () => getJson('/api/freeze-days') });
}
