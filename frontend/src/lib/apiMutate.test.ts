import {afterEach, describe, expect, it, vi} from 'vitest';
import {apiGet, apiMutate, buildApiUrl, getApiErrorMessage} from './apiMutate';


afterEach(() => {
  vi.unstubAllGlobals();
});

describe('getApiErrorMessage', () => {
  it('returns a non-empty error', () => {
    expect(getApiErrorMessage({error: 'Primary'}, 'Fallback')).toBe('Primary');
  });

  it.each([
    null,
    'not an object',
    [],
    {},
    {error: ''},
    {detail: 'Internal FastAPI payload'},
    {error: ['structured']},
  ])('uses fallback for an unusable payload: %j', (payload) => {
    expect(getApiErrorMessage(payload, 'Fallback')).toBe('Fallback');
  });
});

describe('API helpers', () => {
  it('builds encoded URLs while preserving zero and false', () => {
    expect(buildApiUrl('/api/items', {
      empty: '',
      missing: null,
      offset: 0,
      enabled: false,
      search: 'one & two',
    })).toBe('/api/items?offset=0&enabled=false&search=one+%26+two');
  });

  it('uses the same server error for GET and mutation requests', async () => {
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({error: 'Denied'}), {
        status: 403,
        headers: {'Content-Type': 'application/json'},
      }))
      .mockResolvedValueOnce(new Response(JSON.stringify({error: 'Denied'}), {
        status: 403,
        headers: {'Content-Type': 'application/json'},
      })));

    await expect(apiGet('/api/example')).rejects.toThrow('Denied');
    await expect(apiMutate('/api/example', 'POST', {})).rejects.toThrow('Denied');
  });

  it('uses method, URL and status for a non-JSON error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response('not json', {status: 502}),
    ));

    await expect(apiGet('/api/example')).rejects.toThrow('GET /api/example -> 502');
  });
});
