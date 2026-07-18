export function readStoredJson<T>(key: string, fallback: T): T {
  try {
    const value = localStorage.getItem(key);
    return value === null ? fallback : JSON.parse(value) as T;
  } catch {
    return fallback;
  }
}

export function writeStoredJson<T>(key: string, value: T): void {
  localStorage.setItem(key, JSON.stringify(value));
}
