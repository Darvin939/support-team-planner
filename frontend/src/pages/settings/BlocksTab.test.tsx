// @vitest-environment jsdom

import {afterEach, beforeAll, describe, expect, it, vi} from 'vitest';
import {cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {message} from 'antd';
import {WorkReferencesTab} from './BlocksTab';

const mocks = vi.hoisted(() => ({mutate: vi.fn(),
  templates: [{id: 1, name: 'Используемый шаблон', segment_id: 1, blocks: [{id: 1, name: 'Блок', shift_days: 0}]}],
  segments: [{id: 1, name: 'Основной'}],
  blocks: [{id: 1, name: 'Блок'}],
}));
vi.mock('../../lib/apiMutate', () => ({apiMutate: mocks.mutate}));
vi.mock('../../hooks/useSettingsData', () => ({
  useSegments: () => ({data: mocks.segments}),
  useBlocks: () => ({data: mocks.blocks}),
  useBlockTemplates: () => ({data: mocks.templates}),
}));
beforeAll(() => {
  vi.stubGlobal('ResizeObserver', class {observe() {} unobserve() {} disconnect() {}});
  vi.stubGlobal('matchMedia', vi.fn().mockImplementation(() => ({
    matches: false, addListener: vi.fn(), removeListener: vi.fn(),
    addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
  })));
});
afterEach(() => {cleanup(); vi.restoreAllMocks(); mocks.mutate.mockReset();});

function setup() {
  const client = new QueryClient({defaultOptions: {queries: {retry: false}, mutations: {retry: false}}});
  const error = vi.spyOn(message, 'error').mockImplementation(() => (() => {}) as ReturnType<typeof message.error>);
  mocks.mutate.mockRejectedValue(new Error('Шаблон используется работами: удаление и смена сегмента запрещены'));
  render(<QueryClientProvider client={client}><WorkReferencesTab/></QueryClientProvider>);
  return {client, error};
}

describe('template reference errors in settings', () => {
  it('keeps the edit form and user input when saving a used template is rejected', async () => {
    const {client, error} = setup();
    fireEvent.click(screen.getByRole('button', {name: 'Редактировать шаблон'}));
    fireEvent.change(screen.getByRole('textbox', {name: 'Название шаблона'}), {target: {value: 'Моя правка'}});
    fireEvent.click(screen.getByRole('button', {name: 'Обновить'}));
    await waitFor(() => expect(error).toHaveBeenCalledWith(expect.stringContaining('Шаблон используется работами')));
    expect((screen.getByRole('textbox', {name: 'Название шаблона'}) as HTMLInputElement).value).toBe('Моя правка');
    expect(screen.getByRole('dialog')).not.toBeNull();
    expect(screen.getByText('Используемый шаблон')).not.toBeNull();
    client.clear();
  });

  it('keeps the directory row and shows the backend reason when deletion is rejected', async () => {
    const {client, error} = setup();
    fireEvent.click(screen.getByRole('button', {name: 'Удалить шаблон'}));
    fireEvent.click(await screen.findByRole('button', {name: /^Удалить$/}));
    await waitFor(() => expect(error).toHaveBeenCalledWith(expect.stringContaining('Шаблон используется работами')));
    expect(screen.getByText('Используемый шаблон')).not.toBeNull();
    expect(mocks.mutate).toHaveBeenCalledWith('/api/block-templates/1', 'DELETE');
    client.clear();
  });
});
