import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Reports from './Reports';
import type { User } from '../types';

const user: User = { id: '1', name: 'Admin', email: 'admin@example.com', role: 'Administrator', portfolioAccess: [], status: 'Active', defaultLandingPage: 'dashboard', permissions: ['view', 'export'] };
const appPage = { items: [{ id: '1', name: 'Ledger', portfolioName: 'Payments', qualityScore: 80, applicationHealthScore: 75, riskLevel: 'High' }], total: 26, limit: 25, offset: 0 };
const portfolioPage = { items: [{ id: '2', name: 'Payments', owner: 'Team', productArea: 'Finance', applicationCount: 2, qualityScore: 81 }], total: 1, limit: 25, offset: 0 };
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); sessionStorage.clear(); });

it('shows report rows, paginates and selects the portfolio report', async () => {
  const secondAppPage = { items: [{ id: '3', name: 'Billing', portfolioName: 'Commerce', qualityScore: 64, applicationHealthScore: 55, riskLevel: 'Low' }], total: 26, limit: 25, offset: 25 };
  const fetcher = vi.spyOn(globalThis, 'fetch').mockImplementation(async url => {
    const path = String(url);
    return new Response(JSON.stringify(path.includes('portfolios') ? portfolioPage : path.includes('offset=25') ? secondAppPage : appPage));
  });
  render(<MemoryRouter><Reports user={user} /></MemoryRouter>);
  expect(await screen.findByText('Ledger')).toBeTruthy();
  expect((screen.getByRole('button', { name: 'Previous' }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByRole('button', { name: 'Next' }) as HTMLButtonElement).disabled).toBe(false);
  fireEvent.click(screen.getByRole('button', { name: 'Next' }));
  await waitFor(() => expect(fetcher.mock.calls.some(([url]) => String(url).includes('offset=25'))).toBe(true));
  const secondRow = (await screen.findByRole('link', { name: 'Billing' })).closest('tr')!;
  expect(within(secondRow).getByText('Commerce')).toBeTruthy();
  expect(within(secondRow).getByText('64')).toBeTruthy();
  expect(within(secondRow).getByText('55')).toBeTruthy();
  expect(within(secondRow).getByText('Low')).toBeTruthy();
  expect(screen.queryByText('Ledger')).toBeNull();
  expect(screen.getByText('26 total')).toBeTruthy();
  expect((screen.getByRole('button', { name: 'Previous' }) as HTMLButtonElement).disabled).toBe(false);
  expect((screen.getByRole('button', { name: 'Next' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText('Report'), { target: { value: 'portfolios' } });
  expect(await screen.findByText('Payments')).toBeTruthy();
  expect(screen.getByText('81')).toBeTruthy();
});

it('denies the export control to read only and shows empty state', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ items: [], total: 0, limit: 25, offset: 0 })));
  render(<MemoryRouter><Reports user={{ ...user, role: 'Read Only', permissions: ['view', 'export'] }} /></MemoryRouter>);
  expect(await screen.findByText('No records found.')).toBeTruthy();
  expect(screen.queryByRole('button', { name: 'Export CSV' })).toBeNull();
});

it('shows errors and retries and requests a CSV export', async () => {
  let fail = true;
  const fetcher = vi.spyOn(globalThis, 'fetch').mockImplementation(async url => {
    if (fail) return new Response(JSON.stringify({ detail: 'Access denied' }), { status: 403 });
    if (String(url).includes('format=csv')) return new Response('name\nLedger', { headers: { 'content-type': 'text/csv' } });
    return new Response(JSON.stringify(appPage));
  });
  let downloadedBlob: Blob | undefined;
  let downloadedAnchor: HTMLAnchorElement | undefined;
  vi.stubGlobal('URL', Object.assign(class extends URL {}, {
    createObjectURL: vi.fn((blob: Blob) => { downloadedBlob = blob; return 'blob:test'; }),
    revokeObjectURL: vi.fn(),
  }));
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) { downloadedAnchor = this; });
  render(<MemoryRouter><Reports user={user} /></MemoryRouter>);
  expect((await screen.findByRole('alert')).textContent).toContain('Access denied');
  fail = false;
  fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
  expect(await screen.findByText('Ledger')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Export CSV' }));
  await waitFor(() => expect(fetcher.mock.calls.some(([url]) => String(url).includes('/api/reports/applications?format=csv'))).toBe(true));
  await waitFor(() => expect(downloadedAnchor).toBeDefined());
  expect(downloadedAnchor?.download).toBe('applications-report.csv');
  expect(downloadedAnchor?.href).toBe('blob:test');
  expect(downloadedBlob?.type).toBe('text/csv');
  const content = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(downloadedBlob!);
  });
  expect(content).toBe('name\nLedger');
});
