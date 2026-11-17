import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { request } from '../api';
import type { ApplicationSummary, Page, Portfolio, User } from '../types';

/** Show a portfolio and its paginated application references. */
export default function PortfolioDetail({ user }: { user: User }) {
  const { id } = useParams();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const offset = params.get('offset') || '0';
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [applications, setApplications] = useState<Page<ApplicationSummary> | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(false);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    setPortfolio(null);
    setApplications(null);
    Promise.all([request<Portfolio>(`/api/portfolios/${id}`), request<Page<ApplicationSummary>>(`/api/portfolios/${id}/applications?offset=${encodeURIComponent(offset)}`)])
      .then(([p, a]) => { if (active) { setPortfolio(p); setApplications(a); } })
      .catch((err: Error) => { if (active) setError(err.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [id, offset]);
  async function remove() {
    if (!window.confirm('Delete this portfolio and all linked applications? This cannot be undone.')) return;
    setDeleting(true);
    try { await request<void>(`/api/portfolios/${id}`, { method: 'DELETE' }); navigate('/portfolios'); }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to delete portfolio.'); setDeleting(false); }
  }
  const canEdit = user.permissions.includes('edit') && (user.role === 'Administrator' || (user.role === 'Portfolio Leader' && user.portfolioAccess.includes(id || '')));
  return <main className="page">
    <Link to="/portfolios">← Portfolios</Link>
    {loading && <p role="status">Loading portfolio…</p>}
    {error && <p role="alert" className="error">{error}</p>}
    {!loading && portfolio && <>
      <div
        className="portfolio-heading page-heading"
      >
        <div>
          <h1>{portfolio.name}</h1>
          <p
            className="muted"
          >{portfolio.description || 'No description provided.'}</p>
        </div>
        <div
          className="actions"
        >
          {canEdit && <Link
            to={`/portfolios/${id}/edit`}
          >Edit</Link>}
          {user.role === 'Administrator' && user.permissions.includes('delete') && <button
            disabled={deleting}
            onClick={() => void remove()}
          >Delete portfolio</button>}
        </div>
      </div>
      <section
        className="card"
      >
        <h2>Portfolio summary</h2>
        <dl>
          <dt>Owner</dt>
          <dd>{portfolio.owner || '—'}</dd>
          <dt>Product area</dt>
          <dd>{portfolio.productArea || '—'}</dd>
          <dt>Status</dt>
          <dd>{portfolio.status}</dd>
          <dt>Applications</dt>
          <dd>{portfolio.applicationCount}</dd>
          <dt>Quality score</dt>
          <dd>{portfolio.qualityScore ?? '—'}</dd>
        </dl>
      </section>
      <section className="card">
        <h2>Applications</h2>
        {applications && (applications.items.length ? <ul>
          {applications.items.map(app => <li
            key={app.id}
          ><Link
            to={`/applications/${app.id}`}
          >{app.name}</Link> — {app.riskLevel || '—'}</li>)}
        </ul> : <p
          className="muted"
        >No applications found.</p>)}
        {applications && <div
          className="pagination"
        >
          <button
            disabled={applications.offset === 0}
            onClick={() => setParams({ offset: String(Math.max(0, applications.offset - applications.limit)) })}
          >Previous</button>
          <span>{applications.total} total</span>
          <button
            disabled={applications.offset + applications.limit >= applications.total}
            onClick={() => setParams({ offset: String(applications.offset + applications.limit) })}
          >Next</button>
        </div>}
      </section>
    </>}
  </main>;
}
