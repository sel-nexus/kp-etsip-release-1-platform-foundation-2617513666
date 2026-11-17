import { BrowserRouter, Link, NavLink, Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import Login from './auth/Login';
import Profile from './auth/Profile';
import { useAuth } from './auth/useAuth';
import PortfolioList from './portfolios/PortfolioList';
import PortfolioDetail from './portfolios/PortfolioDetail';
import PortfolioForm from './portfolios/PortfolioForm';
import ApplicationList from './applications/ApplicationList';
import ApplicationDetail from './applications/ApplicationDetail';
import ApplicationForm from './applications/ApplicationForm';
import Dashboard from './dashboard/Dashboard';
import Administration from './admin/Administration';
import type { User } from './types';

/** Resolve the persisted landing preference, falling back to the role default. */
function landingPath(user: User): string {
  const landing = user.defaultLandingPage || (['Administrator', 'Executive'].includes(user.role) ? 'dashboard' : 'applications');
  return landing === 'dashboard' ? '/dashboard' : '/applications';
}

/** Wire identity routes to the real API-backed session. */
function IdentityApp() {
  const auth = useAuth();
  const navigate = useNavigate();
  if (auth.loading) return <main className="page" role="status">Restoring session…</main>;
  if (!auth.user) return <Login sessionError={auth.sessionError} onLogin={async (email, password) => { const signedIn = await auth.login(email, password); navigate(landingPath(signedIn), { replace: true }); }} />;
  const user = auth.user;
  return (
    <>
      <header className="topbar">
        <Link className="brand" to="/profile">KP ETSIP <span>Platform Foundation</span></Link>
        <nav aria-label="Account navigation">
          <NavLink to="/dashboard">Dashboard</NavLink>
          <NavLink to="/applications">Applications</NavLink>
          <NavLink to="/portfolios">Portfolios</NavLink>
          {user.role === 'Administrator' && user.permissions.includes('administer') && <NavLink to="/administration">Administration</NavLink>}
          <NavLink to="/profile">My profile</NavLink>
          <button className="quiet" type="button" onClick={() => { void auth.logout(); }}>Sign out</button>
        </nav>
      </header>
      <Routes>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/administration" element={<Administration user={user} />} />
        <Route path="/profile" element={<Profile user={user} onUser={auth.setUser} onSessionEnd={() => { auth.setUser(null); navigate('/'); }} />} />
        <Route path="/portfolios" element={<PortfolioList user={user} />} />
        <Route path="/portfolios/new" element={<PortfolioForm user={user} />} />
        <Route path="/portfolios/:id" element={<PortfolioDetail user={user} />} />
        <Route path="/portfolios/:id/edit" element={<PortfolioForm user={user} />} />
        <Route path="/applications" element={<ApplicationList user={user} />} />
        <Route path="/applications/new" element={<ApplicationForm user={user} />} />
        <Route path="/applications/:id" element={<ApplicationDetail user={user} />} />
        <Route path="/applications/:id/edit" element={<ApplicationForm user={user} />} />
        <Route path="*" element={<Navigate to={landingPath(user)} replace />} />
      </Routes>
    </>
  );
}

export default function App() {
  return <BrowserRouter><IdentityApp /></BrowserRouter>;
}
