import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { request } from '../api';
import type { Application, Page, Portfolio, User } from '../types';

/** Present scoped report data and download authorized CSV snapshots. */
export default function Reports({ user }: { user: User }) {
  const [params, setParams] = useSearchParams();
  const kind = params.get('report') === 'portfolios' ? 'portfolios' : 'applications';
  const offset = Math.max(0, Number(params.get('offset')) || 0);
  const [page, setPage] = useState<Page<Application | Portfolio> | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let active = true;
    setPage(null);
    setLoading(true);
    setError('');
    request<Page<Application | Portfolio>>(`/api/reports/${kind}?limit=25&offset=${offset}`)
      .then(result => { if (active) setPage(result); })
      .catch((err: Error) => { if (active) setError(err.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [kind, offset, retry]);

  function change(nextKind: string, nextOffset = 0) {
    const next = new URLSearchParams();
    next.set('report', nextKind);
    if (nextOffset) next.set('offset', String(nextOffset));
    setParams(next);
  }

  async function download() {
    setExporting(true);
    setError('');
    try {
      const blob = await request<Blob>(`/api/reports/${kind}?format=csv`);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `${kind}-report.csv`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to export report.');
    } finally {
      setExporting(false);
    }
  }

  const canExport = ['Administrator', 'Executive', 'Portfolio Leader', 'Engineer', 'Auditor'].includes(user.role) && user.permissions.includes('view') && user.permissions.includes('export');
  return (
    <main className="page">
      <div className="portfolio-heading">
        <div>
          <h1>Reports</h1>
          <p className="muted">Review visible inventory and export a CSV snapshot.</p>
        </div>
        {canExport && <button type="button" disabled={exporting} onClick={() => void download()}>Export CSV</button>}
      </div>
      <div className="filters">
        <div>
          <label htmlFor="report-kind">Report</label>
          <select id="report-kind" value={kind} onChange={event => change(event.target.value)}>
            <option value="applications">Application Report</option>
            <option value="portfolios">Portfolio Report</option>
          </select>
        </div>
      </div>
      {loading && <p role="status">Loading report…</p>}
      {error && (
        <div role="alert" className="error">
          {error} <button
            type="button"
            className="quiet"
            onClick={() => setRetry(value => value + 1)}
          >Retry</button>
        </div>
      )}
      {!loading && page && (
        <>
          {page.items.length === 0 ? <p>No records found.</p> : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    {(kind === 'applications'
                      ? ['Application', 'Portfolio', 'Quality score', 'Health score', 'Risk level']
                      : ['Portfolio', 'Owner', 'Product area', 'Applications', 'Quality score']
                    ).map(label => <th scope="col" key={label}>{label}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {page.items.map(item => kind === 'applications' ? (
                    <tr key={item.id}>
                      <td>
                        <Link to={`/applications/${item.id}`}>{item.name}</Link>
                      </td>
                      <td>{(item as Application).portfolioName}</td>
                      <td>{item.qualityScore ?? '—'}</td>
                      <td>{(item as Application).applicationHealthScore}</td>
                      <td>{(item as Application).riskLevel}</td>
                    </tr>
                  ) : (
                    <tr key={item.id}>
                      <td>
                        <Link to={`/portfolios/${item.id}`}>{item.name}</Link>
                      </td>
                      <td>{(item as Portfolio).owner}</td>
                      <td>{(item as Portfolio).productArea}</td>
                      <td>{(item as Portfolio).applicationCount}</td>
                      <td>{item.qualityScore ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="pagination">
            <button type="button" disabled={page.offset === 0} onClick={() => change(kind, Math.max(0, page.offset - page.limit))}>Previous</button>
            <span>{page.total} total</span>
            <button
              type="button"
              disabled={page.offset + page.limit >= page.total}
              onClick={() => change(kind, page.offset + page.limit)}
            >Next</button>
          </div>
        </>
      )}
    </main>
  );
}
