import { useState, type FormEvent } from 'react';

interface LoginProps { onLogin: (email: string, password: string) => Promise<void>; sessionError?: string }

/** Present local sign-in and meaningful submission states. */
export default function Login({ onLogin, sessionError }: LoginProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setError('');
    setBusy(true);
    try { await onLogin(email, password); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Sign-in failed. Please try again.'); }
    finally { setBusy(false); }
  }
  return (
    <main className="login-layout">
      <section className="intro" aria-labelledby="welcome-title">
        <p className="eyebrow">KP ETSIP / PLATFORM FOUNDATION</p>
        <h1 id="welcome-title">Quality insights.<br />Shared perspective.</h1>
        <p>Bring portfolio and application quality into focus with a trusted, shared view.</p>
        <div className="intro-foot">ENTERPRISE TECHNOLOGY &amp; STRATEGIC INSIGHTS</div>
      </section>
      <section className="login-panel" aria-labelledby="login-title">
        <div className="form-wrap">
          <p className="eyebrow">WELCOME BACK</p>
          <h2 id="login-title">Sign in</h2>
          <p className="muted">Use your local account to access the platform.</p>
          {(error || sessionError) && <p id="login-error" role="alert" className="error">{error || sessionError}</p>}
          <form onSubmit={submit}>
            <label htmlFor="email">Email address</label>
            <input
              id="email"
              type="email"
              autoComplete="username"
              required
              aria-required="true"
              aria-invalid={!!error}
              aria-describedby={error ? 'login-error' : undefined}
              value={email}
              onChange={event => setEmail(event.target.value)}
            />
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              aria-required="true"
              aria-invalid={!!error}
              aria-describedby={error ? 'login-error' : undefined}
              value={password}
              onChange={event => setPassword(event.target.value)}
            />
            <button type="submit" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
          </form>
          <p className="demo-note">Local demo: admin@ketsip.local. Use the bootstrap password configured by your administrator.</p>
        </div>
      </section>
    </main>
  );
}
