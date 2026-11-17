import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { request } from '../api';
import type { Page, Portfolio, User } from '../types';

/** Display a filterable page of visible portfolio summaries. */
export default function PortfolioList({ user }: { user: User }) {
  const [params, setParams] = useSearchParams();
  const [page, setPage] = useState<Page<Portfolio> | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const query = params.toString();
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    request<Page<Portfolio>>(`/api/portfolios${query ? `?${query}` : ''}`)
      .then(data => { if (active) setPage(data); })
      .catch((err: Error) => { if (active) setError(err.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [query]);
  function change(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    if (key !== 'offset') next.delete('offset');
    setParams(next);
  }
  return (
    <main className="page">
      <div className="portfolio-heading">
        <div><h1>Portfolios</h1><p className="muted">Explore portfolio ownership and application quality.</p></div>
        {user.role === 'Administrator' && user.permissions.includes('create') && <Link className="button-link" to="/portfolios/new">Create portfolio</Link>}
      </div>
      <div className="filters">
        <div><label htmlFor="search">Search</label><input id="search" value={params.get('search') || ''} onChange={e => change('search', e.target.value)} /></div>
        <div><label htmlFor="status">Status</label><select id="status" value={params.get('status') || ''} onChange={e => change('status', e.target.value)}><option value="">All statuses</option><option>Active</option><option>Archived</option></select></div>
        <div><label htmlFor="productArea">Product area</label><input id="productArea" value={params.get('productArea') || ''} onChange={e => change('productArea', e.target.value)} /></div>
      </div>
      {loading && <p role="status">Loading portfolios…</p>}
      {error && <p role="alert" className="error">{error}</p>}
      {!loading && !error && page && <>
        {page.items.length === 0 ? <p>No portfolios found.</p> : <div className="table-wrap"><table>
          <thead><tr><th scope="col">Name</th><th scope="col">Owner</th><th scope="col">Product area</th><th scope="col">Applications</th><th scope="col">Quality score</th><th scope="col">Status</th></tr></thead>
          <tbody>{page.items.map(item => <tr key={item.id}><td><Link to={`/portfolios/${item.id}`}>{item.name}</Link></td><td>{item.owner || '—'}</td><td>{item.productArea || '—'}</td><td>{item.applicationCount}</td><td>{item.qualityScore ?? '—'}</td><td>{item.status}</td></tr>)}</tbody>
        </table></div>}
        <div className="pagination"><button type="button" disabled={page.offset === 0} onClick={() => change('offset', String(Math.max(0, page.offset - page.limit)))}>Previous</button><span>{page.total} total</span><button type="button" disabled={page.offset + page.limit >= page.total} onClick={() => change('offset', String(page.offset + page.limit))}>Next</button></div>
      </>}
    </main>
  );
}
