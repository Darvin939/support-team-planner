export interface ApiResult {
  success?: boolean;
  error?: string;
  id?: number;
  task_completion_suggestion?: {
    task_id: number;
    task_name: string;
  };
}

interface ApiErrorPayload {
  error?: unknown;
}

function nonEmptyString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value : null;
}

export function getApiErrorMessage(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return fallback;
  const {error} = payload as ApiErrorPayload;
  return nonEmptyString(error) ?? fallback;
}

async function readApiError(response: Response, method: string, url: string): Promise<Error> {
  const fallback = `${method} ${url} -> ${response.status}`;
  const payload: unknown = await response.json().catch(() => null);
  return new Error(getApiErrorMessage(payload, fallback));
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
export async function apiMutate<T extends ApiResult = ApiResult>(
  url: string,
  method: 'POST' | 'PUT' | 'PATCH' | 'DELETE',
  body?: unknown,
): Promise<T> {
  const r = await fetch(url, {
    method,
    credentials: 'same-origin',
    headers: body !== undefined ? {'Content-Type': 'application/json'} : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw await readApiError(r, method, url);
  return await r.json().catch(() => ({})) as T;
}

/** GET helper — returns the parsed JSON body and throws with the server's `error` message on a
 * non-2xx response, mirroring apiMutate's error-message preference (server message first). */
export async function apiGet<T>(url: string): Promise<T> {
  const r = await fetch(url, {credentials: 'same-origin'});
  if (!r.ok) throw await readApiError(r, 'GET', url);
  return await r.json().catch(() => ({})) as T;
}
