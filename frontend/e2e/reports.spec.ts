import { expect, test } from '@playwright/test';
import { readFile } from 'node:fs/promises';

test('reports display real scoped inventory and export both CSVs', async ({ page }) => {
  const password = process.env.E2E_PASSWORD;
  if (!password) throw new Error('Set E2E_PASSWORD to the configured demo bootstrap password');
  const errors: string[] = [];
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await page.getByLabel('Email address').fill('admin@ketsip.local');
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('link', { name: 'Reports', exact: true })).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem('ketsip-token'));
  const headers = { Authorization: `Bearer ${token}` };
  const name = `Reports journey ${Date.now()}`;
  const created = await page.request.post('/api/portfolios', { headers, data: { name } });
  expect(created.status()).toBe(201);
  const portfolio = await created.json();
  try {
    const application = await page.request.post('/api/applications', { headers, data: { name: `${name} app`, portfolioId: portfolio.id, qualityScore: 83 } });
    expect(application.status()).toBe(201);
    await page.getByRole('link', { name: 'Reports', exact: true }).click();
    // Fetch all pages until the test record is visible.
    await expect(page.getByRole('button', { name: 'Next' })).toBeVisible();
    while (!(await page.getByText(`${name} app`, { exact: true }).count())) {
      const next = page.getByRole('button', { name: 'Next' });
      if (await next.isDisabled()) throw new Error('Application missing from report');
      const response = page.waitForResponse(res => res.url().includes('/api/reports/applications?') && res.request().method() === 'GET');
      await next.click();
      expect((await response).ok()).toBeTruthy();
      await expect(page.getByRole('button', { name: 'Next' })).toBeVisible();
    }
    const appDownload = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Export CSV' }).click();
    const downloadedApp = await appDownload;
    expect(downloadedApp.suggestedFilename()).toBe('applications-report.csv');
    expect(await readFile((await downloadedApp.path())!, 'utf8')).toContain(`${name} app`);
    await page.getByRole('link', { name: `${name} app`, exact: true }).click();
    await expect(page.getByRole('heading', { name: `${name} app` })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Application details' })).toBeVisible();
    await expect(page.getByText('Quality score', { exact: true }).locator('..')).toContainText('83');
    await page.getByRole('link', { name: 'Reports', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Next' })).toBeVisible();
    const portfolioResponse = page.waitForResponse(res => res.url().includes('/api/reports/portfolios?') && res.request().method() === 'GET');
    await page.getByLabel('Report').selectOption('portfolios');
    expect((await portfolioResponse).ok()).toBeTruthy();
    await expect(page.getByRole('button', { name: 'Next' })).toBeVisible();
    while (!(await page.getByText(name, { exact: true }).count())) {
      const next = page.getByRole('button', { name: 'Next' });
      if (await next.isDisabled()) throw new Error('Portfolio missing from report');
      const response = page.waitForResponse(res => res.url().includes('/api/reports/portfolios?') && res.request().method() === 'GET');
      await next.click();
      expect((await response).ok()).toBeTruthy();
      await expect(page.getByRole('button', { name: 'Next' })).toBeVisible();
    }
    await expect(page.getByText(name, { exact: true }).locator('xpath=ancestor::tr')).toContainText('83');
    const portfolioDownload = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Export CSV' }).click();
    const downloadedPortfolio = await portfolioDownload;
    expect(downloadedPortfolio.suggestedFilename()).toBe('portfolios-report.csv');
    expect(await readFile((await downloadedPortfolio.path())!, 'utf8')).toContain(name);
    await page.getByRole('link', { name, exact: true }).click();
    await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Portfolio summary' })).toBeVisible();
    await expect(page.getByRole('link', { name: `${name} app` })).toBeVisible();
  } finally {
    expect((await page.request.delete(`/api/portfolios/${portfolio.id}`, { headers })).status()).toBe(204);
  }
  expect(errors).toEqual([]);
});
