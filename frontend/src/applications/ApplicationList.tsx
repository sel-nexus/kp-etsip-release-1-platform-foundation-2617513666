import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { request } from '../api';
import type { Application, Page, Portfolio, User } from '../types';

/** Display and export the visible, filtered application inventory. */
export default function ApplicationList({ user }: { user: User }) {
  const [params, setParams] = useSearchParams();
  const [page, setPage] = useState<Page<Application> | null>(null);
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const query = params.toString();
  useEffect(() => {
    let active = true;
    setLoading(true); setError('');
    request<Page<Application>>(`/api/applications${query ? `?${query}` : ''}`)
      .then(data => { if (active) setPage(data); })
      .catch((err: Error) => { if (active) setError(err.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [query]);
  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const all: Portfolio[] = [];
        let offset = 0;
        do {
          const result = await request<Page<Portfolio>>(`/api/portfolios?limit=100&offset=${offset}`);
          all.push(...result.items); offset += result.items.length;
          if (!result.items.length || offset >= result.total) break;
        } while (true);
        if (active) setPortfolios(all);
      } catch (err) { if (active) setError(err instanceof Error ? err.message : 'Unable to load portfolios.'); }
    }
    void load();
    return () => { active = false; };
  }, []);
  function change(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    if (key !== 'offset') next.delete('offset');
    setParams(next);
  }
  async function download() {
    setExporting(true); setError('');
    try {
      const exportParams = new URLSearchParams(params);
      exportParams.delete('limit'); exportParams.delete('offset'); exportParams.set('format', 'csv');
      const blob = await request<Blob>(`/api/applications?${exportParams}`);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'applications.csv'; anchor.click();
      URL.revokeObjectURL(url);
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to export applications.'); }
    finally { setExporting(false); }
  }
  const canCreate = ['Administrator', 'Engineer', 'Portfolio Leader'].includes(user.role) && user.permissions.includes('create');
  const canExport = user.role !== 'Read Only' && user.permissions.includes('export');
  return (
    <main className="page">
      <div className="portfolio-heading">
        <div>
          <h1>Application repository</h1>
          <p className="muted">Review application ownership, quality and risk.</p>
        </div>
        <div className="actions">
          {canExport && <button type="button" disabled={exporting} onClick={() => void download()}>Export CSV</button>}
          {canCreate && <Link className="button-link" to="/applications/new">Create application</Link>}
        </div>
      </div>
      <div className="filters">
        <div>
          <label
            htmlFor="app-search"
          >Search</label>
          <input
            id="app-search"
            maxLength={200}
            value={params.get('search') || ''}
            onChange={e => change('search', e.target.value)}
          />
        </div>
        <div>
          <label
            htmlFor="app-portfolio"
          >Portfolio</label>
          <select
            id="app-portfolio"
            value={params.get('portfolioId') || ''}
            onChange={e => change('portfolioId', e.target.value)}
          >
            <option
              value=""
            >All portfolios</option>
            {portfolios.map(p => <option
              key={p.id}
              value={p.id}
            >{p.name}</option>)}
          </select>
        </div>
        {[
          ['criticality', 'Criticality', ['Low', 'Medium', 'High', 'Critical']],
          ['riskLevel', 'Risk level', ['Low', 'Medium', 'High']],
          ['lifecycleStatus', 'Lifecycle status', ['Active', 'Deprecated', 'Retired']]
        ].map(([key, label, options]) => <div
          key={key as string}
        >
          <label
            htmlFor={`filter-${key}`}
          >{label as string}</label>
          <select
            id={`filter-${key}`}
            value={params.get(key as string) || ''}
            onChange={e => change(key as string, e.target.value)}
          >
            <option
              value=""
            >All</option>
            {(options as string[]).map(option => <option
              key={option}
            >{option}</option>)}
          </select>
        </div>)}
      </div>
      {loading && <p role="status">Loading applications…</p>}
      {error && <p role="alert" className="error">{error}</p>}
      {!loading && page && <>
        {page.items.length === 0 ? <p>No applications found.</p> : <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {[
                  'Name', 'Portfolio', 'Criticality', 'Tier', 'Lifecycle status', 'Health score',
                  'Automation coverage', 'Open critical defects', 'Risk level'
                ].map(label => <th
                  scope="col"
                  key={label}
                >{label}</th>)}
              </tr>
            </thead>
            <tbody>
              {page.items.map(item => <tr
                key={item.id}
              >
                <td>
                  <Link
                    to={`/applications/${item.id}`}
                  >{item.name}</Link>
                </td>
                <td>{item.portfolioName || item.portfolioId}</td>
                <td>{item.criticality}</td>
                <td>{item.tier}</td>
                <td>{item.lifecycleStatus}</td>
                <td>{item.applicationHealthScore}</td>
                <td>{item.automationCoverage}%</td>
                <td>{item.openCriticalDefects}</td>
                <td>{item.riskLevel}</td>
              </tr>)}
            </tbody>
          </table>
        </div>}
        <div
          className="pagination"
        >
          <button
            disabled={page.offset === 0}
            onClick={() => change('offset', String(Math.max(0, page.offset - page.limit)))}
          >Previous</button>
          <span>{page.total} total</span>
          <button
            disabled={page.offset + page.limit >= page.total}
            onClick={() => change('offset', String(page.offset + page.limit))}
          >Next</button>
        </div>
      </>}
    </main>
  );
}
