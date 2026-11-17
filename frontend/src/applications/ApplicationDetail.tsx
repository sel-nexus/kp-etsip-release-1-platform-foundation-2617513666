import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { request } from '../api';
import type { Application, User } from '../types';

/** Show application details and authorized actions. */
export default function ApplicationDetail({ user }: { user: User }) {
  const { id } = useParams();
  const navigate = useNavigate();
  const [app, setApp] = useState<Application | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(false);
  useEffect(() => {
    let active = true;
    request<Application>(`/api/applications/${id}`).then(data => { if (active) setApp(data); })
      .catch((err: Error) => { if (active) setError(err.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [id]);
  async function remove() {
    if (!window.confirm('Delete this application? This cannot be undone.')) return;
    setDeleting(true); setError('');
    try { await request<void>(`/api/applications/${id}`, { method: 'DELETE' }); navigate('/applications'); }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to delete application.'); setDeleting(false); }
  }
  const canEdit = app && user.permissions.includes('edit') && (['Administrator', 'Engineer'].includes(user.role) || (user.role === 'Portfolio Leader' && user.portfolioAccess.includes(app.portfolioId)));
  const fields: [string, string | number | null][] = app ? [
    ['Description', app.description], ['Portfolio', app.portfolioName || app.portfolioId], ['Product area', app.productArea],
    ['Business owner', app.businessOwner], ['Technology owner', app.technologyOwner], ['ETS owner', app.etsOwner],
    ['Criticality', app.criticality], ['Tier', app.tier], ['Lifecycle status', app.lifecycleStatus], ['Technology stack', app.technologyStack],
    ['Application health score', app.applicationHealthScore], ['Quality score', app.qualityScore], ['Automation coverage', `${app.automationCoverage}%`],
    ['Unit-test coverage', `${app.unitTestCoverage}%`], ['Open defects', app.openDefects], ['Open critical defects', app.openCriticalDefects], ['Risk level', app.riskLevel],
  ] : [];
  return (
    <main className="page">
      <Link to="/applications">← Applications</Link>
      {loading && <p role="status">Loading application…</p>}
      {error && <p role="alert" className="error">{error}</p>}
      {app && <>
        <div className="portfolio-heading page-heading">
          <h1>{app.name}</h1>
          <div className="actions">
            {canEdit && <Link to={`/applications/${id}/edit`}>Edit</Link>}
            {user.role === 'Administrator' && user.permissions.includes('delete') && <button disabled={deleting} onClick={() => void remove()}>Delete application</button>}
          </div>
        </div>
        <section className="card">
          <h2>Application details</h2>
          <dl>
            {fields.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value === '' || value === null ? '—' : value}</dd></div>)}
            <dt>Repository link</dt><dd>{app.repositoryLink ? <a href={app.repositoryLink} target="_blank" rel="noreferrer">{app.repositoryLink}</a> : '—'}</dd>
            <dt>Pipeline link</dt><dd>{app.pipelineLink ? <a href={app.pipelineLink} target="_blank" rel="noreferrer">{app.pipelineLink}</a> : '—'}</dd>
          </dl>
        </section>
      </>}
    </main>
  );
}
