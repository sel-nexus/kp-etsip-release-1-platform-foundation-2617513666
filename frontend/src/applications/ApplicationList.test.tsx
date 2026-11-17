import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import ApplicationList from './ApplicationList';
import ApplicationForm from './ApplicationForm';
import ApplicationDetail from './ApplicationDetail';
import type { User } from '../types';

const user: User = { id: '1', name: 'Admin', email: 'admin', role: 'Administrator', portfolioAccess: [], status: 'Active', defaultLandingPage: 'applications', permissions: ['view', 'create', 'edit', 'delete', 'export'] };
const item = { id: 'a1', name: 'Ledger', portfolioId: 'p1', portfolioName: 'Payments', description: 'Core', productArea: 'Finance', businessOwner: 'Business', technologyOwner: 'Tech', etsOwner: 'ETS', criticality: 'High', tier: 2, lifecycleStatus: 'Active', technologyStack: 'Python', repositoryLink: null, pipelineLink: null, applicationHealthScore: 80, qualityScore: 90, automationCoverage: 70, unitTestCoverage: 60, openDefects: 2, openCriticalDefects: 1, riskLevel: 'High', createdAt: '', updatedAt: '' };
const portfolioPage = { items: [{ id: 'p1', name: 'Payments' }], total: 1, limit: 100, offset: 0 };
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('application inventory', () => {
  it('renders API data and filters using URL parameters', async () => {
    const fetcher = vi.spyOn(globalThis, 'fetch').mockImplementation(async url => new Response(JSON.stringify(String(url).includes('/portfolios') ? portfolioPage : { items: [item], total: 1, limit: 25, offset: 0 }), { status: 200 }));
    render(<MemoryRouter><ApplicationList user={user} /></MemoryRouter>);
    expect(await screen.findByRole('link', { name: 'Ledger' })).toBeTruthy();
    expect(screen.getByText('70%')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Export CSV' })).toBeTruthy();
    fireEvent.change(screen.getByLabelText('Risk level'), { target: { value: 'High' } });
    await waitFor(() => expect(fetcher.mock.calls.some(([url]) => String(url).includes('riskLevel=High'))).toBe(true));
  });
  it('hides restricted actions and reports API failures', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async url => String(url).includes('/portfolios') ? new Response(JSON.stringify(portfolioPage)) : new Response(JSON.stringify({ detail: 'Denied' }), { status: 403 }));
    render(<MemoryRouter><ApplicationList user={{ ...user, role: 'Read Only', permissions: ['view', 'export', 'create'] }} /></MemoryRouter>);
    expect((await screen.findByRole('alert')).textContent).toBe('Denied');
    expect(screen.queryByRole('link', { name: 'Create application' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Export CSV' })).toBeNull();
  });
  it('shows detail fields and hides edit and delete from read only', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify(item)));
    render(<MemoryRouter initialEntries={['/applications/a1']}><Routes><Route path="/applications/:id" element={<ApplicationDetail user={{ ...user, role: 'Read Only', permissions: ['view'] }} />} /></Routes></MemoryRouter>);
    expect(await screen.findByRole('heading', { name: 'Ledger' })).toBeTruthy();
    expect(screen.getByText('Business')).toBeTruthy();
    expect(screen.queryByRole('link', { name: 'Edit' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Delete application' })).toBeNull();
  });
  it('submits form values and surfaces save failure', async () => {
    const fetcher = vi.spyOn(globalThis, 'fetch').mockImplementation(async (_url, options) => options?.method === 'POST' ? new Response(JSON.stringify({ detail: 'Application name already exists' }), { status: 409 }) : new Response(JSON.stringify(portfolioPage)));
    render(<MemoryRouter initialEntries={['/applications/new']}><ApplicationForm user={user} /></MemoryRouter>);
    await screen.findByRole('option', { name: 'Payments' });
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Ledger' } });
    fireEvent.change(screen.getByLabelText('Portfolio'), { target: { value: 'p1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save application' }));
    expect((await screen.findByRole('alert')).textContent).toBe('Application name already exists');
    const submitted = fetcher.mock.calls.find(([, options]) => options?.method === 'POST');
    expect(JSON.parse(String(submitted?.[1]?.body))).toMatchObject({ name: 'Ledger', portfolioId: 'p1', qualityScore: 0 });
  });
});
