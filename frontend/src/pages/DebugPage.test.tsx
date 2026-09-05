// @vitest-environment jsdom
import {render, screen} from '@testing-library/react';
import {MemoryRouter} from 'react-router-dom';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {describe, expect, it, vi} from 'vitest';
import {DebugPage} from './DebugPage';

vi.mock('../hooks/useMe', () => ({useMe: () => ({data: {role: 'admin', login: 'other'}, isLoading: false})}));

describe('DebugPage access', () => {
  it('does not render the console for another admin login', () => {
    const client = new QueryClient({defaultOptions: {queries: {retry: false}}});
    render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/debug']}><DebugPage/></MemoryRouter></QueryClientProvider>);
    expect(screen.queryByText('Отладка')).toBeNull();
  });
});
