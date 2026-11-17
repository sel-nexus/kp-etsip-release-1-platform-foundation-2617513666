import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { request } from '../api';
import type { DashboardMetrics, Page, Portfolio } from '../types';

/** Present live, scoped quality and risk metrics with shareable filters. */
export default function Dashboard() {
  const [params, setParams] = useSearchParams();
  const [data, setData] = useState<DashboardMetrics | null>(null);
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  const query = params.toString();

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    async function load() {
      try {
        const metrics = await request<DashboardMetrics>(`/api/dashboard/executive${query ? `?${query}` : ''}`);
        const items: Portfolio[] = [];
        let offset = 0;
        let total = 0;
        do {
          const page = await request<Page<Portfolio>>(`/api/portfolios?limit=100&offset=${offset}`);
          items.push(...page.items);
          total = page.total;
          offset += page.items.length;
          if (!page.items.length) break;
        } while (offset < total);
        if (active) { setData(metrics); setPortfolios(items); }
      } catch (reason) {
        if (active) setError(reason instanceof Error ? reason.message : 'Unable to load the dashboard.');
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    return () => { active = false; };
  }, [query, retry]);

  function filter(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    setParams(next);
  }
  const areas = Array.from(new Set(portfolios.map(item => item.productArea).filter(Boolean))).sort();
  const display = (value: number | null) => value === null ? '—' : value.toString();
  const cards: [string, number | null][] = data ? [
    ['Enterprise Quality Score', data.enterpriseQualityScore],
    ['Application Health Score', data.applicationHealthScore],
    ['Automation Maturity Score', data.automationMaturityScore],
    ['Open Critical Defects', data.openCriticalDefects],
    ['Applications at Risk', data.applicationsAtRisk],
    ['Total Applications', data.totalApplications],
    ['Total Portfolios', data.totalPortfolios],
  ] : [];

  return (
    <main className="page">
      <div className="page-heading">
        <p className="eyebrow">QUALITY INSIGHTS</p>
        <h1>Executive Dashboard</h1>
        <p className="muted">Quality and risk across your visible inventory.</p>
      </div>
      <div className="filters" aria-label="Dashboard filters">
        <div>
          <label htmlFor="dashboard-portfolio">Portfolio</label>
          <select id="dashboard-portfolio" value={params.get('portfolioId') || ''} onChange={event => filter('portfolioId', event.target.value)}>
            <option value="">All portfolios</option>
            {portfolios.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="dashboard-area">Product area</label>
          <select id="dashboard-area" value={params.get('productArea') || ''} onChange={event => filter('productArea', event.target.value)}>
            <option value="">All product areas</option>
            {areas.map(area => <option key={area} value={area}>{area}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="dashboard-risk">Risk level</label>
          <select id="dashboard-risk" value={params.get('riskLevel') || ''} onChange={event => filter('riskLevel', event.target.value)}>
            <option value="">All risk levels</option>
            <option value="Low">Low</option><option value="Medium">Medium</option><option value="High">High</option>
          </select>
        </div>
        <button className="quiet dashboard-clear" type="button" onClick={() => setParams({})}>Clear filters</button>
      </div>
      {loading && <p role="status">Loading dashboard…</p>}
      {!loading && error && <div role="alert" className="error">{error} <button type="button" onClick={() => setRetry(value => value + 1)}>Retry</button></div>}
      {!loading && !error && data && <>
        {data.totalApplications === 0 && <p role="status" className="muted">No applications match the selected filters.</p>}
        <dl className="dashboard-metrics">
          {cards.map(([label, value]) => <div className="card dashboard-metric" key={label}><dt>{label}</dt><dd>{display(value)}</dd></div>)}
        </dl>
        <div className="dashboard-bars">
          <section className="card" aria-labelledby="quality-bars">
            <h2 id="quality-bars">Portfolio Quality Score</h2>
            {!data.portfolios.length && <p className="muted">No portfolios match the selected filters.</p>}
            <ul>{data.portfolios.map(item => <li key={item.id}>
              <div className="bar-label"><span>{item.name}</span><strong>{display(item.qualityScore)}</strong></div>
              <div className="bar-track" aria-hidden="true"><div className="bar-fill" style={{ width: `${item.qualityScore ?? 0}%` }} /></div>
            </li>)}</ul>
          </section>
          <section className="card" aria-labelledby="risk-bars">
            <h2 id="risk-bars">Applications at Risk by portfolio</h2>
            {!data.portfolios.length && <p className="muted">No portfolios match the selected filters.</p>}
            <ul>{data.portfolios.map(item => <li key={item.id}>
              <div className="bar-label"><span>{item.name}</span><strong>{item.applicationsAtRisk} of {item.applicationCount}</strong></div>
              <div className="bar-track" aria-hidden="true"><div className="bar-fill" style={{ width: `${item.applicationCount ? item.applicationsAtRisk / item.applicationCount * 100 : 0}%` }} /></div>
            </li>)}</ul>
          </section>
        </div>
      </>}
    </main>
  );
}
