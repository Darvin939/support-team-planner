export interface ApiResult {
  success?: boolean;
  error?: string;
  id?: number;
}

export function buildApiUrl(path: string, params: Record<string, string | number | boolean | null | undefined>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') search.set(key, String(value));
  });
  const query = search.toString();
  return query ? `${path}?${query}` : path;
}

/** POST/PUT/DELETE helper — returns the parsed JSON body and throws with the server's
 * `error` message (matching this app's `{"error": "..."}` convention) on a non-2xx response. */
export async function apiMutate(url: string, method: 'POST' | 'PUT' | 'PATCH' | 'DELETE', body?: unknown): Promise<ApiResult> {
  const r = await fetch(url, {
    method,
    credentials: 'same-origin',
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const data: ApiResult = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || `${method} ${url} -> ${r.status}`);
  return data;
}

/** GET helper — returns the parsed JSON body and throws with the server's `error` message on a
 * non-2xx response, mirroring apiMutate's error-message preference (server message first). */
export async function apiGet<T>(url: string): Promise<T> {
  const r = await fetch(url, { credentials: 'same-origin' });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error((data as ApiResult).error || `GET ${url} -> ${r.status}`);
  return data as T;
}
