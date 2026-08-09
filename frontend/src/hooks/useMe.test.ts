import {QueryClient, QueryObserver} from '@tanstack/react-query';
import {describe, expect, it, vi} from 'vitest';
import {meQueryOptions, type Me} from './useMe';


const me: Me = {
  user_id: 1,
  role: 'admin',
  last_name: null,
  first_name: 'Admin',
  middle_name: null,
};


describe('useMe query policy', () => {
  it('reuses fresh data when a second observer mounts', async () => {
    const queryClient = new QueryClient();
    const queryFn = vi.fn().mockResolvedValue(me);
    const options = {...meQueryOptions, queryFn};
    const firstObserver = new QueryObserver(queryClient, options);
    const unsubscribeFirst = firstObserver.subscribe(() => undefined);

    await firstObserver.refetch();
    unsubscribeFirst();

    const secondObserver = new QueryObserver(queryClient, options);
    const unsubscribeSecond = secondObserver.subscribe(() => undefined);
    await Promise.resolve();

    expect(secondObserver.getCurrentResult().data).toEqual(me);
    expect(queryFn).toHaveBeenCalledTimes(1);

    unsubscribeSecond();
    queryClient.clear();
  });
});
