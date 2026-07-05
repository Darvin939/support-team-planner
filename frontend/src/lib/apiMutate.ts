export interface ApiResult {
  success?: boolean;
  error?: string;
  id?: number;
}

/** POST/PUT/DELETE helper — returns the parsed JSON body and throws with the server's
 * `error` message (matching this app's `{"error": "..."}` convention) on a non-2xx response. */
export async function apiMutate(url: string, method: 'POST' | 'PUT' | 'DELETE', body?: unknown): Promise<ApiResult> {
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
