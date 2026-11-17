import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import PortfolioList from './PortfolioList';
import type { User } from '../types';

const user: User = { id: '1', name: 'Admin', email: 'a', role: 'Administrator', portfolioAccess: [], status: 'Active', defaultLandingPage: 'dashboard', permissions: ['view', 'create'] };
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('portfolio list', () => {
  it('renders API metrics and filters using URL parameters', async () => {
    const fetcher = vi.spyOn(globalThis, 'fetch').mockImplementation(async () => new Response(JSON.stringify({ items: [{ id: 'p1', name: 'Payments', owner: 'Team', productArea: 'Finance', applicationCount: 2, qualityScore: 85, status: 'Active' }], total: 1, limit: 25, offset: 0 }), { status: 200 }));
    render(<MemoryRouter><PortfolioList user={user} /></MemoryRouter>);
    expect(await screen.findByRole('link', { name: 'Payments' })).toBeTruthy();
    expect(screen.getByText('85')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Create portfolio' })).toBeTruthy();
    fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'Active' } });
    await screen.findByText('85');
    expect(fetcher.mock.calls.some(([url]) => String(url).includes('status=Active'))).toBe(true);
  });
  it('reports errors and hides creation from read-only users', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ detail: 'Denied' }), { status: 403 }));
    render(<MemoryRouter><PortfolioList user={{ ...user, role: 'Read Only', permissions: ['view'] }} /></MemoryRouter>);
    expect((await screen.findByRole('alert')).textContent).toBe('Denied');
    expect(screen.queryByRole('link', { name: 'Create portfolio' })).toBeNull();
  });
});
