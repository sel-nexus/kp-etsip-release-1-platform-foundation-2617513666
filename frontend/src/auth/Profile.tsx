import { useState, type FormEvent } from 'react';
import { request, TOKEN_KEY } from '../api';
import type { User } from '../types';

interface ProfileProps { user: User; onUser: (user: User) => void; onSessionEnd: () => void }

/** Show account details and persist preferences and password changes. */
export default function Profile({ user, onUser, onSessionEnd }: ProfileProps) {
  const [landing, setLanding] = useState(user.defaultLandingPage);
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  async function savePreference(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setMessage('');
    try {
      const updated = await request<User>('/api/profile', { method: 'PUT', body: JSON.stringify({ defaultLandingPage: landing }) });
      onUser(updated); setMessage('Preference saved.');
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to save preference.'); }
    finally { setBusy(false); }
  }
  async function changePassword(event: FormEvent) {
    event.preventDefault(); setError(''); setMessage('');
    if (next !== confirm) { setError('New passwords do not match.'); return; }
    setBusy(true);
    try {
      await request<void>('/api/profile/password', { method: 'PUT', body: JSON.stringify({ currentPassword: current, newPassword: next }) });
      sessionStorage.removeItem(TOKEN_KEY); onSessionEnd();
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to change password.'); }
    finally { setBusy(false); }
  }
  return (
    <main className="page">
      <div className="page-heading">
        <p className="eyebrow">ACCOUNT SETTINGS</p>
        <h1>My profile</h1>
        <p className="muted">Manage your account preferences and security.</p>
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      {message && <p className="success" role="status">{message}</p>}
      <div className="profile-grid">
        <section className="card" aria-labelledby="details-title">
          <h2 id="details-title">Account details</h2>
          <dl>
            <dt>Name</dt>
            <dd>{user.name}</dd>
            <dt>Email</dt>
            <dd>{user.email}</dd>
            <dt>Role</dt>
            <dd>{user.role}</dd>
            <dt>Portfolio access</dt>
            <dd>{user.portfolioAccess.length
              ? user.portfolioAccess.join(', ')
              : user.role === 'Portfolio Leader' ? 'No assigned portfolios' : 'All portfolios'}</dd>
          </dl>
        </section>
        <div className="stack">
          <section className="card" aria-labelledby="preference-title">
            <h2 id="preference-title">Landing preference</h2>
            <p className="muted">Choose where you start after signing in.</p>
            <form onSubmit={savePreference}>
              <label htmlFor="landing">Default landing page</label>
              <select id="landing" value={landing} onChange={event => setLanding(event.target.value as User['defaultLandingPage'])}>
                <option value="dashboard">Executive Dashboard</option>
                <option value="applications">Application Repository</option>
              </select>
              <button disabled={busy} type="submit">Save preference</button>
            </form>
          </section>
          <section className="card" aria-labelledby="security-title">
            <h2 id="security-title">Change password</h2>
            <p className="muted">Use at least 12 characters. You will need to sign in again.</p>
            <form onSubmit={changePassword}>
              <label htmlFor="current-password">Current password</label>
              <input
                id="current-password"
                type="password"
                required
                autoComplete="current-password"
                value={current}
                onChange={event => setCurrent(event.target.value)}
              />
              <label htmlFor="new-password">New password</label>
              <input
                id="new-password"
                type="password"
                required
                minLength={12}
                maxLength={72}
                autoComplete="new-password"
                value={next}
                onChange={event => setNext(event.target.value)}
              />
              <label htmlFor="confirm-password">Confirm new password</label>
              <input
                id="confirm-password"
                type="password"
                required
                minLength={12}
                maxLength={72}
                autoComplete="new-password"
                value={confirm}
                onChange={event => setConfirm(event.target.value)}
              />
              <button disabled={busy} type="submit">Change password</button>
            </form>
          </section>
        </div>
      </div>
    </main>
  );
}
