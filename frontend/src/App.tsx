import { BrowserRouter, Link, NavLink, Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import Login from './auth/Login';
import Profile from './auth/Profile';
import { useAuth } from './auth/useAuth';
import PortfolioList from './portfolios/PortfolioList';
import PortfolioDetail from './portfolios/PortfolioDetail';
import PortfolioForm from './portfolios/PortfolioForm';

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
          <NavLink to="/portfolios">Portfolios</NavLink>
          <NavLink to="/profile">My profile</NavLink>
          <button className="quiet" type="button" onClick={() => { void auth.logout(); }}>Sign out</button>
        </nav>
      </header>
      <Routes>
        <Route path="/profile" element={<Profile user={user} onUser={auth.setUser} onSessionEnd={() => { auth.setUser(null); navigate('/'); }} />} />
        <Route path="/portfolios" element={<PortfolioList user={user} />} />
        <Route path="/portfolios/new" element={<PortfolioForm user={user} />} />
        <Route path="/portfolios/:id" element={<PortfolioDetail user={user} />} />
        <Route path="/portfolios/:id/edit" element={<PortfolioForm user={user} />} />
        <Route path="*" element={<Navigate to="/profile" replace />} />
      </Routes>
    </>
  );
}

export default function App() {
  return <BrowserRouter><IdentityApp /></BrowserRouter>;
}
