import { useState } from 'react';
import type { FormEvent } from 'react';
import type { AdminRole } from '../types';

interface Props { role: AdminRole; onSave: (role: AdminRole) => Promise<void>; onCancel: () => void }
const permissions = ['view', 'create', 'edit', 'delete', 'export', 'administer'];

/** Edit a role's permissions, subject to server-side hard limits. */
export default function RoleForm({ role, onSave, onCancel }: Props) {
  const [description, setDescription] = useState(role.description);
  const [selected, setSelected] = useState(role.permissions);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try { await onSave({ ...role, description, permissions: selected }); }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to save role'); }
    finally { setBusy(false); }
  }
  return (
    <form className="card portfolio-form" onSubmit={submit}>
      <h2>{role.id ? 'Edit' : 'Create'} {role.name}</h2>
      <label htmlFor="role-description">Description</label>
      <input id="role-description" value={description} maxLength={500} onChange={event => setDescription(event.target.value)} />
      <fieldset>
        <legend>Permissions</legend>
        {permissions.map(permission => (
          <label className="admin-check" key={permission}>
            <input type="checkbox" checked={selected.includes(permission)} onChange={event => setSelected(event.target.checked ? [...selected, permission] : selected.filter(item => item !== permission))} />
            {permission}
          </label>
        ))}
      </fieldset>
      <p className="muted">Resource-specific role restrictions still apply even when a permission is enabled.</p>
      {error && <p role="alert" className="error">{error}</p>}
      <div className="actions">
        <button type="submit" disabled={busy}>Save role</button>
        <button type="button" className="quiet" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}
