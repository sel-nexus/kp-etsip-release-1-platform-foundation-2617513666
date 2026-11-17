import { FormEvent, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { request } from '../api';
import type { Application, ApplicationInput, Page, Portfolio, User } from '../types';

const empty: ApplicationInput = { name: '', description: '', portfolioId: '', productArea: '', businessOwner: '', technologyOwner: '', etsOwner: '', criticality: 'Low', tier: 1, lifecycleStatus: 'Active', technologyStack: '', repositoryLink: null, pipelineLink: null, applicationHealthScore: 0, qualityScore: 0, automationCoverage: 0, unitTestCoverage: 0, openDefects: 0, openCriticalDefects: 0, riskLevel: 'Low' };
const textFields: [keyof ApplicationInput, string, number][] = [['name', 'Name', 200], ['description', 'Description', 4000], ['productArea', 'Product area', 200], ['businessOwner', 'Business owner', 200], ['technologyOwner', 'Technology owner', 200], ['etsOwner', 'ETS owner', 200], ['technologyStack', 'Technology stack', 4000], ['repositoryLink', 'Repository link', 2048], ['pipelineLink', 'Pipeline link', 2048]];
const numbers: [keyof ApplicationInput, string, number | undefined, number][] = [['tier', 'Tier', 4, 1], ['applicationHealthScore', 'Application health score', 100, 0], ['qualityScore', 'Quality score', 100, 0], ['automationCoverage', 'Automation coverage %', 100, 0], ['unitTestCoverage', 'Unit-test coverage %', 100, 0], ['openDefects', 'Open defects', undefined, 0], ['openCriticalDefects', 'Open critical defects', undefined, 0]];

/** Create or edit all application fields through the API. */
export default function ApplicationForm({ user }: { user: User }) {
  const { id } = useParams();
  const navigate = useNavigate();
  const [form, setForm] = useState<ApplicationInput>(empty);
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [failed, setFailed] = useState(false);
  const permitted = ['Administrator', 'Engineer', 'Portfolio Leader'].includes(user.role) && user.permissions.includes(id ? 'edit' : 'create');
  useEffect(() => {
    if (!permitted) { setLoading(false); return; }
    let active = true;
    async function load() {
      try {
        const all: Portfolio[] = [];
        let offset = 0;
        do {
          const page = await request<Page<Portfolio>>(`/api/portfolios?limit=100&offset=${offset}`);
          all.push(...page.items); offset += page.items.length;
          if (!page.items.length || offset >= page.total) break;
        } while (true);
        const app = id ? await request<Application>(`/api/applications/${id}`) : null;
        if (active) {
          setPortfolios(all);
          if (app) {
            const values = Object.fromEntries(Object.keys(empty).map(key => [key, app[key as keyof Application]])) as unknown as ApplicationInput;
            setForm(values);
          }
        }
      } catch (err) { if (active) { setError(err instanceof Error ? err.message : 'Unable to load application.'); setFailed(true); } }
      finally { if (active) setLoading(false); }
    }
    void load();
    return () => { active = false; };
  }, [id, permitted]);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!form.name.trim()) { setError('Name is required.'); return; }
    setError(''); setSaving(true);
    try {
      const saved = await request<Application>(id ? `/api/applications/${id}` : '/api/applications', { method: id ? 'PUT' : 'POST', body: JSON.stringify(form) });
      navigate(`/applications/${saved.id}`);
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to save application.'); setSaving(false); }
  }
  return (
    <main className="page">
      <Link to={id ? `/applications/${id}` : '/applications'}>← Back</Link>
      <h1>{id ? 'Edit application' : 'Create application'}</h1>
      {!permitted ? <p
        role="alert"
      >You cannot change applications.</p> : loading ? <p
        role="status"
      >Loading application…</p> : failed ? <p
        role="alert"
        className="error"
      >{error}</p> :
        <form className="portfolio-form" onSubmit={submit}>
          {textFields.map(([key, label, max]) => <div key={key}>
            <label htmlFor={`field-${key}`}>{label}</label>
            <input
              id={`field-${key}`}
              type={key === 'repositoryLink' || key === 'pipelineLink' ? 'url' : 'text'}
              required={key === 'name'}
              aria-required={key === 'name'}
              maxLength={max}
              value={String(form[key] ?? '')}
              onChange={e => setForm({ ...form, [key]: e.target.value || (key === 'repositoryLink' || key === 'pipelineLink' ? null : '') })}
            />
          </div>)}
          <label htmlFor="field-portfolio">Portfolio</label>
          <select
            id="field-portfolio"
            required
            aria-required="true"
            value={form.portfolioId}
            onChange={e => setForm({ ...form, portfolioId: e.target.value })}
          >
            <option value="">Select a portfolio</option>
            {portfolios.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          {([
            ['criticality', 'Criticality', ['Low', 'Medium', 'High', 'Critical']],
            ['lifecycleStatus', 'Lifecycle status', ['Active', 'Deprecated', 'Retired']],
            ['riskLevel', 'Risk level', ['Low', 'Medium', 'High']]
          ] as [keyof ApplicationInput, string, string[]][]).map(([key, label, options]) => <div
            key={key}
          >
            <label htmlFor={`field-${key}`}>{label}</label>
            <select
              id={`field-${key}`}
              value={String(form[key])}
              onChange={e => setForm({ ...form, [key]: e.target.value })}
            >
              {options.map(option => <option
                key={option}
              >{option}</option>)}
            </select>
          </div>)}
          {numbers.map(([key, label, max, min]) => <div key={key}>
            <label htmlFor={`field-${key}`}>{label}</label>
            <input
              id={`field-${key}`}
              type="number"
              required
              min={min}
              max={max}
              step={1}
              value={String(form[key])}
              onChange={e => setForm({ ...form, [key]: e.target.value === '' ? '' : Number(e.target.value) })}
            />
          </div>)}
          {error && <p role="alert" className="error">{error}</p>}
          <button type="submit" disabled={saving}>Save application</button>
        </form>}
    </main>
  );
}
