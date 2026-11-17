import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Administration from './Administration';
import type { User } from '../types';

const admin: User = { id: '1', name: 'Admin', email: 'admin@example.com', role: 'Administrator', status: 'Active', portfolioAccess: [], defaultLandingPage: 'dashboard', permissions: ['administer'] };
const page = (items: unknown[]) => ({ items, total: items.length, limit: 25, offset: 0 });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('administration', () => {
  it('renders users, creates an account with assigned portfolio, and displays API errors', async () => {
    const fetcher = vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, options) => {
      if (options?.method === 'POST') return new Response(JSON.stringify({ detail: 'Email already exists' }), { status: 409 });
      const path = String(url);
      const data = path.includes('/api/users') ? page([admin]) : path.includes('/api/roles') ? page([{ id: 'r', name: 'Read Only', description: '', permissions: ['view'] }]) : page([{ id: 'p', name: 'Payments' }]);
      return new Response(JSON.stringify(data), { status: 200, headers: { 'Content-Type': 'application/json' } });
    });
    render(<MemoryRouter><Administration user={admin} /></MemoryRouter>);
    fireEvent.click(await screen.findByRole('button', { name: 'Create user' }));
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Test' } });
    fireEvent.change(screen.getByLabelText('Email address'), { target: { value: 'test@example.com' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'Password-12345' } });
    fireEvent.change(screen.getByLabelText('Assigned portfolios'), { target: { value: 'p' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save user' }));
    expect((await screen.findByRole('alert')).textContent).toBe('Email already exists');
    expect(fetcher.mock.calls.some(([url, init]) => String(url) === '/api/users' && String(init?.body).includes('test@example.com'))).toBe(true);
  });
  it('denies non-administrators and does not fetch data', () => {
    const fetcher = vi.spyOn(globalThis, 'fetch');
    render(<MemoryRouter><Administration user={{ ...admin, role: 'Auditor' }} /></MemoryRouter>);
    expect(screen.getByRole('alert').textContent).toContain('do not have access');
    expect(fetcher).not.toHaveBeenCalled();
  });
  it('edits role permissions and filters audit history', async () => {
    const fetcher = vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, options) => {
      const path = String(url);
      if (options?.method === 'PUT') return new Response(JSON.stringify({}), { status: 200 });
      const data = path.includes('audit-logs') ? page([{ id: 'a', timestamp: '2026-01-01T00:00:00Z', userId: '1', userName: 'Admin', action: 'edit', entityType: 'role', entityId: 'r', details: 'Role edit' }]) : path.includes('/api/users') ? page([admin]) : path.includes('/api/roles') ? page([{ id: 'r', name: 'Read Only', description: '', permissions: ['view'] }]) : page([]);
      return new Response(JSON.stringify(data), { status: 200, headers: { 'Content-Type': 'application/json' } });
    });
    render(<MemoryRouter><Administration user={admin} /></MemoryRouter>);
    await screen.findByRole('button', { name: 'Create user' });
    fireEvent.click(screen.getByRole('button', { name: 'Roles' }));
    fireEvent.click(screen.getByRole('button', { name: 'Edit Read Only' }));
    fireEvent.click(screen.getByLabelText('export'));
    fireEvent.click(screen.getByRole('button', { name: 'Save role' }));
    await waitFor(() => expect(fetcher.mock.calls.some(([url, init]) => String(url).includes('/api/roles/r') && String(init?.body).includes('export'))).toBe(true));
    fireEvent.click(screen.getByRole('button', { name: 'Audit' }));
    expect(await screen.findByText('Role edit')).toBeTruthy();
    fireEvent.change(screen.getByLabelText('Action'), { target: { value: 'edit' } });
    await waitFor(() => expect(fetcher.mock.calls.some(([url]) => String(url).includes('action=edit'))).toBe(true));
  });
});
