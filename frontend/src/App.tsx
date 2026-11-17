import { BrowserRouter, Link, Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import Login from './auth/Login';
import Profile from './auth/Profile';
import { useAuth } from './auth/useAuth';

/** Wire identity routes to the real API-backed session. */
function IdentityApp() {
  const auth = useAuth();
  const navigate = useNavigate();
  if (auth.loading) return <main className="page" role="status">Restoring session…</main>;
  if (!auth.user) return <Login sessionError={auth.sessionError} onLogin={async (email, password) => { await auth.login(email, password); navigate('/profile'); }} />;
  const user = auth.user;
  return (
    <>
      <header className="topbar">
        <Link className="brand" to="/profile">KP ETSIP <span>Platform Foundation</span></Link>
        <nav aria-label="Account navigation">
          <Link to="/profile" aria-current="page">My profile</Link>
          <button className="quiet" type="button" onClick={() => { void auth.logout(); }}>Sign out</button>
        </nav>
      </header>
      <Routes>
        <Route path="/profile" element={<Profile user={user} onUser={auth.setUser} onSessionEnd={() => { auth.setUser(null); navigate('/'); }} />} />
        <Route path="*" element={<Navigate to="/profile" replace />} />
      </Routes>
    </>
  );
}

export default function App() {
  return <BrowserRouter><IdentityApp /></BrowserRouter>;
}
