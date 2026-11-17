import { FormEvent, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { request } from '../api';
import type { Portfolio, PortfolioInput, User } from '../types';

/** Create or edit portfolio fields using the real API. */
export default function PortfolioForm({ user }: { user: User }) {
  const { id } = useParams();
  const navigate = useNavigate();
  const [form, setForm] = useState<PortfolioInput>({ name: '', owner: '', description: '', productArea: '', status: 'Active' });
  const [loading, setLoading] = useState(Boolean(id));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [loadFailed, setLoadFailed] = useState(false);
  const permitted = id ? user.permissions.includes('edit') && (user.role === 'Administrator' || (user.role === 'Portfolio Leader' && user.portfolioAccess.includes(id))) : user.role === 'Administrator' && user.permissions.includes('create');
  useEffect(() => {
    if (!id || !permitted) { setLoading(false); return; }
    let active = true;
    request<Portfolio>(`/api/portfolios/${id}`).then(p => { if (active) setForm({ name: p.name, owner: p.owner, description: p.description, productArea: p.productArea, status: p.status }); })
      .catch((err: Error) => { if (active) { setError(err.message); setLoadFailed(true); } }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [id, permitted]);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!form.name.trim()) { setError('Name is required.'); return; }
    setError(''); setSaving(true);
    try {
      const saved = await request<Portfolio>(id ? `/api/portfolios/${id}` : '/api/portfolios', { method: id ? 'PUT' : 'POST', body: JSON.stringify(form) });
      navigate(`/portfolios/${saved.id}`);
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to save portfolio.'); setSaving(false); }
  }
  return <main className="page">
    <Link to={id ? `/portfolios/${id}` : '/portfolios'}>← Back</Link>
    <h1>{id ? 'Edit portfolio' : 'Create portfolio'}</h1>
    {!permitted ? <p
      role="alert"
    >You cannot change this portfolio.</p> : loading ? <p
      role="status"
    >Loading portfolio…</p> : loadFailed ? <p
      role="alert"
      className="error"
    >{error}</p> : <form
      className="portfolio-form"
      onSubmit={submit}
    >
      <label
        htmlFor="name"
      >Name</label>
      <input
        id="name"
        required
        maxLength={200}
        value={form.name}
        onChange={e => setForm({ ...form, name: e.target.value })}
      />
      <label htmlFor="owner">Owner</label>
      <input id="owner" maxLength={200} value={form.owner} onChange={e => setForm({ ...form, owner: e.target.value })} />
      <label
        htmlFor="area"
      >Product area</label>
      <input
        id="area"
        maxLength={200}
        value={form.productArea}
        onChange={e => setForm({ ...form, productArea: e.target.value })}
      />
      <label
        htmlFor="description"
      >Description</label>
      <textarea
        id="description"
        maxLength={4000}
        value={form.description}
        onChange={e => setForm({ ...form, description: e.target.value })}
      />
      <label
        htmlFor="form-status"
      >Status</label>
      <select
        id="form-status"
        value={form.status}
        onChange={e => setForm({ ...form, status: e.target.value as PortfolioInput['status'] })}
      >
        <option>Active</option>
        <option>Archived</option>
      </select>
      {error && <p role="alert" className="error">{error}</p>}
      <button type="submit" disabled={saving}>Save portfolio</button>
    </form>}
  </main>;
}
