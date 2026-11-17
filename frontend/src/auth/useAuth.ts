import { useCallback, useEffect, useState } from 'react';
import { request, TOKEN_KEY } from '../api';
import type { LoginResponse, User } from '../types';

/** Manage the current session, including server-side invalidation. */
export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(Boolean(sessionStorage.getItem(TOKEN_KEY)));
  const [sessionError, setSessionError] = useState('');

  useEffect(() => {
    const expired = () => { setUser(null); setSessionError('Your session has ended. Please sign in again.'); };
    window.addEventListener('auth-expired', expired);
    if (sessionStorage.getItem(TOKEN_KEY)) {
      request<User>('/api/auth/me').then(setUser).catch(() => { setSessionError('Unable to restore your session. Please sign in again.'); }).finally(() => setLoading(false));
    }
    return () => window.removeEventListener('auth-expired', expired);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const response = await request<LoginResponse>('/api/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) });
    sessionStorage.setItem(TOKEN_KEY, response.token);
    setUser(response.user);
    setSessionError('');
    return response.user;
  }, []);

  const logout = useCallback(async () => {
    try { await request<void>('/api/auth/logout', { method: 'POST' }); }
    catch { setSessionError('Signed out locally. The server could not revoke this session.'); }
    finally { sessionStorage.removeItem(TOKEN_KEY); setUser(null); }
  }, []);

  return { user, setUser, loading, sessionError, login, logout };
}
