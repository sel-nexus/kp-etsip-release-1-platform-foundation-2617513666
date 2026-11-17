import { useState } from 'react';
import type { FormEvent } from 'react';
import type { AdminRole, AdminUserInput, Portfolio, User } from '../types';

interface Props { user: User | null; roles: AdminRole[]; portfolios: Portfolio[]; onSave: (value: AdminUserInput) => Promise<void>; onCancel: () => void }

/** Edit an account and its portfolio assignments. */
export default function UserForm({ user, roles, portfolios, onSave, onCancel }: Props) {
  const [name, setName] = useState(user?.name || '');
  const [email, setEmail] = useState(user?.email || '');
  const [role, setRole] = useState(user?.role || 'Read Only');
  const [status, setStatus] = useState(user?.status || 'Active');
  const [password, setPassword] = useState('');
  const [scope, setScope] = useState<string[]>(user?.portfolioAccess || []);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setError(''); setBusy(true);
    try { await onSave({ name, email, role, status, portfolioAccess: scope, ...(password ? { password } : {}) }); }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to save user'); }
    finally { setBusy(false); }
  }
  return (
    <form className="card portfolio-form" onSubmit={submit}>
      <h2>{user ? 'Edit user' : 'Create user'}</h2>
      <label htmlFor="admin-name">Name</label>
      <input id="admin-name" value={name} onChange={e => setName(e.target.value)} required maxLength={200} />
      <label htmlFor="admin-email">Email address</label>
      <input id="admin-email" type="email" value={email} onChange={e => setEmail(e.target.value)} required maxLength={254} />
      <label htmlFor="admin-password">{user ? 'New password (optional)' : 'Password'}</label>
      <input id="admin-password" type="password" autoComplete="new-password" value={password} onChange={e => setPassword(e.target.value)} required={!user} minLength={12} maxLength={72} />
      <label htmlFor="admin-role">Role</label>
      <select id="admin-role" value={role} onChange={e => setRole(e.target.value)}>
        {roles.map(item => <option key={item.id} value={item.name}>{item.name}</option>)}
      </select>
      <label htmlFor="admin-status">Status</label>
      <select id="admin-status" value={status} onChange={e => setStatus(e.target.value)}>
        <option>Active</option><option>Inactive</option>
      </select>
      <label htmlFor="admin-scope">Assigned portfolios</label>
      <select id="admin-scope" multiple value={scope} onChange={e => setScope(Array.from(e.target.selectedOptions, option => option.value))}>
        {portfolios.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select>
      <p className="muted">Hold Ctrl or Command to select multiple portfolios. Empty leader scope grants no access.</p>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="actions">
        <button disabled={busy} type="submit">Save user</button>
        <button className="quiet" type="button" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}
