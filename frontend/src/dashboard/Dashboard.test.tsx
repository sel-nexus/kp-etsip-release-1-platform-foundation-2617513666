import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Dashboard from './Dashboard';
import App from '../App';

const metrics = { enterpriseQualityScore: 81, applicationHealthScore: 50, automationMaturityScore: 61, openCriticalDefects: 5, applicationsAtRisk: 1, totalApplications: 2, totalPortfolios: 1, portfolios: [{ id: 'one', name: 'Payments', applicationCount: 2, qualityScore: 81, applicationsAtRisk: 1 }] };
const page = { items: [{ id: 'one', name: 'Payments', productArea: 'Finance' }], total: 1, offset: 0, limit: 100 };
afterEach(() => { cleanup(); vi.restoreAllMocks(); sessionStorage.clear(); window.history.replaceState({}, '', '/'); });

it('renders metrics and bars and applies shareable filters', async () => {
  const fetcher = vi.spyOn(globalThis, 'fetch').mockImplementation(async url => {
    const path = String(url);
    if (path.includes('/portfolios')) return new Response(JSON.stringify(page));
    const params = new URL(path, 'http://localhost').searchParams;
    const portfolio = params.get('portfolioId') === 'one';
    const area = params.get('productArea') === 'Finance';
    const highRisk = params.get('riskLevel') === 'High';
    const score = portfolio && area && highRisk ? 43 : portfolio && area ? 67 : portfolio ? 74 : 81;
    const atRisk = portfolio && area && highRisk ? 2 : 1;
    return new Response(JSON.stringify({ ...metrics, enterpriseQualityScore: score, applicationsAtRisk: atRisk, portfolios: [{ ...metrics.portfolios[0], qualityScore: score, applicationsAtRisk: atRisk }] }));
  });
  render(<MemoryRouter><Dashboard /></MemoryRouter>);
  expect(await screen.findByRole('heading', { name: 'Portfolio Quality Score' })).toBeTruthy();
  expect(screen.getByText('Enterprise Quality Score').nextElementSibling?.textContent).toBe('81');
  expect(within(screen.getByRole('region', { name: 'Applications at Risk by portfolio' })).getByText('1 of 2')).toBeTruthy();
  fireEvent.change(screen.getByLabelText('Portfolio'), { target: { value: 'one' } });
  await waitFor(() => expect(screen.getByText('Enterprise Quality Score').nextElementSibling?.textContent).toBe('74'));
  fireEvent.change(screen.getByLabelText('Product area'), { target: { value: 'Finance' } });
  await waitFor(() => expect(fetcher.mock.calls.some(([url]) => String(url).includes('productArea=Finance'))).toBe(true));
  await waitFor(() => expect(screen.getByText('Enterprise Quality Score').nextElementSibling?.textContent).toBe('67'));
  fireEvent.change(screen.getByLabelText('Risk level'), { target: { value: 'High' } });
  await waitFor(() => expect(fetcher.mock.calls.some(([url]) => String(url).includes('riskLevel=High'))).toBe(true));
  await waitFor(() => expect(screen.getByText('Enterprise Quality Score').nextElementSibling?.textContent).toBe('43'));
  expect(within(screen.getByRole('region', { name: 'Applications at Risk by portfolio' })).getByText('2 of 2')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }));
  expect((screen.getByLabelText('Risk level') as HTMLSelectElement).value).toBe('');
  await waitFor(() => expect(screen.getByText('Enterprise Quality Score').nextElementSibling?.textContent).toBe('81'));
  expect(within(screen.getByRole('region', { name: 'Applications at Risk by portfolio' })).getByText('1 of 2')).toBeTruthy();
});

it('shows loading, empty averages and no matching applications', async () => {
  let release!: (value: Response) => void;
  vi.spyOn(globalThis, 'fetch').mockImplementation(url => String(url).includes('/portfolios') ? Promise.resolve(new Response(JSON.stringify({ ...page, items: [], total: 0 }))) : new Promise(resolve => { release = resolve; }));
  render(<MemoryRouter><Dashboard /></MemoryRouter>);
  expect(screen.getByRole('status').textContent).toContain('Loading');
  release(new Response(JSON.stringify({ ...metrics, enterpriseQualityScore: null, applicationHealthScore: null, automationMaturityScore: null, totalApplications: 0, totalPortfolios: 0, portfolios: [] })));
  expect(await screen.findByText('No applications match the selected filters.')).toBeTruthy();
  expect(screen.getByText('Enterprise Quality Score').nextElementSibling?.textContent).toBe('—');
});

it('exposes errors and retries', async () => {
  let fail = true;
  vi.spyOn(globalThis, 'fetch').mockImplementation(async url => {
    if (fail) return new Response(JSON.stringify({ detail: 'Access denied' }), { status: 403 });
    return new Response(JSON.stringify(String(url).includes('/portfolios') ? page : metrics));
  });
  render(<MemoryRouter><Dashboard /></MemoryRouter>);
  expect((await screen.findByRole('alert')).textContent).toContain('Access denied');
  fail = false;
  fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
  expect(await screen.findByText('Enterprise Quality Score')).toBeTruthy();
});

it('uses the user returned by login for the persisted landing preference', async () => {
  const user = { id: '1', name: 'Executive', email: 'executive@ketsip.local', role: 'Executive', portfolioAccess: [], status: 'Active', defaultLandingPage: 'dashboard', permissions: ['view'] };
  vi.spyOn(globalThis, 'fetch').mockImplementation(async url => {
    const path = String(url);
    if (path.includes('/auth/login')) return new Response(JSON.stringify({ token: 'test-token', user }));
    return new Response(JSON.stringify(path.includes('/portfolios') ? page : metrics));
  });
  render(<App />);
  fireEvent.change(screen.getByLabelText('Email address'), { target: { value: user.email } });
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'password' } });
  fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
  expect(await screen.findByRole('heading', { name: 'Executive Dashboard' })).toBeTruthy();
  expect(window.location.pathname).toBe('/dashboard');
});

it('redirects a restored session at root to its saved applications preference', async () => {
  sessionStorage.setItem('ketsip-token', 'test-token');
  const user = { id: '1', name: 'Admin', email: 'admin@ketsip.local', role: 'Administrator', portfolioAccess: [], status: 'Active', defaultLandingPage: 'applications', permissions: ['view'] };
  vi.spyOn(globalThis, 'fetch').mockImplementation(async url => {
    if (String(url).includes('/auth/me')) return new Response(JSON.stringify(user));
    return new Response(JSON.stringify({ items: [], total: 0, limit: 100, offset: 0 }));
  });
  render(<App />);
  expect(await screen.findByRole('heading', { name: 'Application repository' })).toBeTruthy();
  expect(window.location.pathname).toBe('/applications');
});
