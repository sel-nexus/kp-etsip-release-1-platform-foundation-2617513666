import { useEffect, useState } from 'react';
import { request } from '../api';
import type { AuditEntry, Page, User } from '../types';

/** Filter administrative history and download the matching CSV. */
export default function AuditLog({ users }: { users: User[] }) {
  const [userId, setUserId] = useState('');
  const [action, setAction] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<Page<AuditEntry> | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const query = new URLSearchParams();
  if (userId) query.set('userId', userId);
  if (action) query.set('action', action);
  if (startDate) query.set('startDate', startDate);
  if (endDate) query.set('endDate', endDate);
  const filters = query.toString();
  useEffect(() => {
    let live = true;
    setLoading(true); setError('');
    request<Page<AuditEntry>>(`/api/audit-logs?${filters}&offset=${offset}`).then(result => { if (live) setPage(result); }).catch(err => { if (live) setError(err instanceof Error ? err.message : 'Unable to load audit history'); }).finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [filters, offset]);
  async function download() {
    try {
      const blob = await request<Blob>(`/api/audit-logs?${filters}&format=csv`);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a'); link.href = url; link.download = 'audit-logs.csv'; link.click(); URL.revokeObjectURL(url);
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to export audit history'); }
  }
  return (
    <section aria-label="Audit history">
      <div className="filters">
        <div><label htmlFor="audit-user">User ID</label><input id="audit-user" list="audit-users" value={userId} onChange={e => { setUserId(e.target.value); setOffset(0); }} /><datalist id="audit-users">{users.map(user => <option key={user.id} value={user.id}>{user.name}</option>)}</datalist></div>
        <div><label htmlFor="audit-action">Action</label><input id="audit-action" value={action} onChange={e => { setAction(e.target.value); setOffset(0); }} /></div>
        <div><label htmlFor="audit-start">From date</label><input id="audit-start" type="date" value={startDate} onChange={e => { setStartDate(e.target.value); setOffset(0); }} /></div>
        <div><label htmlFor="audit-end">To date</label><input id="audit-end" type="date" value={endDate} onChange={e => { setEndDate(e.target.value); setOffset(0); }} /></div>
        <button type="button" onClick={() => void download()}>Export CSV</button>
      </div>
      {error && <p role="alert" className="error">{error}</p>}
      {loading && <p role="status">Loading audit history…</p>}
      {!loading && page && <>
        <div className="table-wrap"><table><thead><tr><th scope="col">Date</th><th scope="col">User</th><th scope="col">Action</th><th scope="col">Entity</th><th scope="col">Details</th></tr></thead><tbody>
          {page.items.map(item => <tr key={item.id}><td>{new Date(item.timestamp).toLocaleString()}</td><td>{item.userName}</td><td>{item.action}</td><td>{item.entityType}</td><td>{item.details}</td></tr>)}
        </tbody></table></div>
        {!page.total && <p className="muted">No audit events found.</p>}
        <div className="pagination"><button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 25))}>Previous</button><span>{page.total} events</span><button type="button" disabled={offset + 25 >= page.total} onClick={() => setOffset(offset + 25)}>Next</button></div>
      </>}
    </section>
  );
}
