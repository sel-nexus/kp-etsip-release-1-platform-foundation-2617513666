/** Call the API with the current bearer token and normalized error messages. */
export const TOKEN_KEY = 'ketsip-token';

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = sessionStorage.getItem(TOKEN_KEY);
  const headers = new Headers(options.headers);
  if (options.body) headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || ''}${path}`, { ...options, headers });
  if (!response.ok) {
    if (response.status === 401 && path !== '/api/auth/login') {
      sessionStorage.removeItem(TOKEN_KEY);
      window.dispatchEvent(new Event('auth-expired'));
    }
    const body = await response.json().catch(() => null) as { detail?: unknown } | null;
    throw new ApiError(response.status, typeof body?.detail === 'string' ? body.detail : 'Unable to complete the request.');
  }
  if (response.status === 204) return undefined as T;
  if (response.headers.get('content-type')?.includes('text/csv')) return await response.blob() as T;
  return await response.json() as T;
}
