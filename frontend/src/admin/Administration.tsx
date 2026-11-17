import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { request } from '../api';
import type { AdminRole, AdminUserInput, Page, Portfolio, User } from '../types';
import UserForm from './UserForm';
import RoleForm from './RoleForm';
import AuditLog from './AuditLog';

/** Manage users, roles, and administrative audit history. */
export default function Administration({ user }: { user: User }) {
  const [params, setParams] = useSearchParams();
  const tab = params.get('tab') || 'users';
  const [users, setUsers] = useState<Page<User> | null>(null);
  const [roles, setRoles] = useState<AdminRole[]>([]);
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [editing, setEditing] = useState<User | 'new' | null>(null);
  const [roleEdit, setRoleEdit] = useState<AdminRole | null>(null);
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const allowed = user.role === 'Administrator' && user.permissions.includes('administer');
  useEffect(() => {
    if (!allowed) return;
    let live = true; setLoading(true); setError('');
    async function load() {
      const [u, r] = await Promise.all([request<Page<User>>(`/api/users?limit=25&offset=${offset}`), request<Page<AdminRole>>('/api/roles?limit=100')]);
      const all: Portfolio[] = [];
      let start = 0; let total = 0;
      do {
        const p = await request<Page<Portfolio>>(`/api/admin/portfolios?limit=100&offset=${start}`);
        all.push(...p.items); total = p.total; start += 100;
      } while (start < total);
      if (live) { setUsers(u); setRoles(r.items); setPortfolios(all); }
    }
    load().catch(err => { if (live) setError(err instanceof Error ? err.message : 'Unable to load administration'); }).finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [allowed, offset, revision]);
  if (!allowed) return <main className="page">
    <h1>Administration</h1>
    <p role="alert">You do not have access to administration.</p>
  </main>;
  async function saveUser(value: AdminUserInput) {
    await request(editing === 'new' ? '/api/users' : `/api/users/${(editing as User).id}`, { method: editing === 'new' ? 'POST' : 'PUT', body: JSON.stringify(value) });
    setEditing(null); setRevision(n => n + 1);
  }
  async function saveRole(value: AdminRole) {
    const { id, ...body } = value;
    await request(id ? `/api/roles/${id}` : '/api/roles', { method: id ? 'PUT' : 'POST', body: JSON.stringify(body) });
    setRoleEdit(null); setRevision(n => n + 1);
  }
  async function remove(item: User) {
    if (!window.confirm(`Delete ${item.name}? Audit history will be retained.`)) return;
    try { await request(`/api/users/${item.id}`, { method: 'DELETE' }); setRevision(n => n + 1); }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to delete user'); }
  }
  const missing = ['Administrator', 'Executive', 'Portfolio Leader', 'Engineer', 'Auditor', 'Read Only'].filter(name => !roles.some(role => role.name === name));
  return (
    <main className="page">
      <div className="page-heading">
        <h1>Administration</h1>
        <p className="muted">Manage access and review activity.</p>
      </div>
      <nav aria-label="Administration sections" className="admin-tabs">
        {['users', 'roles', 'audit'].map(item => <button
          key={item}
          className="quiet"
          type="button"
          aria-current={tab === item ? 'page' : undefined}
          onClick={() => { setParams({ tab: item }); setEditing(null); setRoleEdit(null); }}
        >{item[0].toUpperCase() + item.slice(1)}</button>)}
      </nav>
      {error && <p role="alert" className="error">{error}</p>}
      {loading && <p role="status">Loading administration…</p>}
      {!loading && users && tab === 'users' && <section>
        {editing ? <UserForm
          key={editing === 'new' ? 'new' : editing.id}
          user={editing === 'new' ? null : editing}
          roles={roles}
          portfolios={portfolios}
          onSave={saveUser}
          onCancel={() => setEditing(null)}
        /> : <>
          <div className="portfolio-heading">
            <h2>Users</h2>
            <button type="button" onClick={() => setEditing('new')}>Create user</button>
          </div>
          <div
            className="table-wrap"
          >
            <table>
              <thead>
                <tr>
                  <th
                    scope="col"
                  >Name</th>
                  <th
                    scope="col"
                  >Email</th>
                  <th
                    scope="col"
                  >Role</th>
                  <th
                    scope="col"
                  >Status</th>
                  <th
                    scope="col"
                  >Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.items.map(item => <tr
                  key={item.id}
                >
                  <td>{item.name}</td>
                  <td>{item.email}</td>
                  <td>{item.role}</td>
                  <td>{item.status}</td>
                  <td>
                    <button
                      className="quiet"
                      type="button"
                      onClick={() => setEditing(item)}
                    >Edit {item.name}</button>
                    <button
                      className="quiet"
                      type="button"
                      onClick={() => void remove(item)}
                    >Delete {item.name}</button>
                  </td>
                </tr>)}
              </tbody>
            </table>
          </div>
          {!users.total && <p className="muted">No users found.</p>}
          <div
            className="pagination"
          >
            <button
              type="button"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - 25))}
            >Previous</button>
            <span>{users.total} users</span>
            <button
              type="button"
              disabled={offset + 25 >= users.total}
              onClick={() => setOffset(offset + 25)}
            >Next</button>
          </div>
        </>}
      </section>}
      {!loading && tab === 'roles' && <section>
        {roleEdit ? <RoleForm key={roleEdit.id || roleEdit.name} role={roleEdit} onSave={saveRole} onCancel={() => setRoleEdit(null)} /> : <>
          <h2>Roles</h2>
          <div
            className="table-wrap"
          >
            <table>
              <thead>
                <tr>
                  <th
                    scope="col"
                  >Role</th>
                  <th
                    scope="col"
                  >Permissions</th>
                  <th
                    scope="col"
                  >Action</th>
                </tr>
              </thead>
              <tbody>
                {roles.map(role => <tr
                  key={role.id}
                >
                  <td>{role.name}</td>
                  <td>{role.permissions.join(', ')}</td>
                  <td>
                    <button
                      className="quiet"
                      type="button"
                      onClick={() => setRoleEdit(role)}
                    >Edit {role.name}</button>
                  </td>
                </tr>)}
              </tbody>
            </table>
          </div>
          {missing.map(name => <button
            key={name}
            className="quiet"
            type="button"
            onClick={() => setRoleEdit({ id: '', name, description: '', permissions: [] })}
          >Create {name}</button>)}
        </>}
      </section>}
      {!loading && users && tab === 'audit' && <AuditLog users={users.items} />}
    </main>
  );
}
