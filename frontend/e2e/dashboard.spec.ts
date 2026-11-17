import { expect, test } from '@playwright/test';

test('dashboard reflects real inventory, filters and saved landing preference', async ({ page }) => {
  const password = process.env.E2E_PASSWORD;
  if (!password) throw new Error('Set E2E_PASSWORD to the configured demo bootstrap password');
  const errors: string[] = [];
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await page.getByLabel('Email address').fill('admin@ketsip.local');
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('link', { name: 'Dashboard', exact: true })).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem('ketsip-token'));
  expect(token).toBeTruthy();
  const headers = { Authorization: `Bearer ${token}` };
  const me = await page.request.get('/api/auth/me', { headers });
  expect(me.ok()).toBeTruthy();
  const previousLanding = (await me.json()).defaultLandingPage;
  const name = `Dashboard journey ${Date.now()}`;
  const created = await page.request.post('/api/portfolios', { headers, data: { name, productArea: 'Dashboard test area' } });
  expect(created.status()).toBe(201);
  const portfolio = await created.json();
  try {
    const application = await page.request.post('/api/applications', { headers, data: {
      name: `${name} app`, portfolioId: portfolio.id, qualityScore: 83,
      applicationHealthScore: 77, automationCoverage: 64, openCriticalDefects: 3, riskLevel: 'High',
    } });
    expect(application.status()).toBe(201);
    await page.getByRole('link', { name: 'Dashboard', exact: true }).click();
    await page.getByLabel('Portfolio', { exact: true }).selectOption(portfolio.id);
    await expect(page.getByText('Enterprise Quality Score').locator('..').locator('dd')).toHaveText('83');
    await expect(page.getByText('Open Critical Defects').locator('..').locator('dd')).toHaveText('3');
    await expect(page.getByRole('region', { name: 'Applications at Risk by portfolio' }).getByText('1 of 1')).toBeVisible();
    await page.getByLabel('Risk level').selectOption('Low');
    await expect(page.getByText('No applications match the selected filters.')).toBeVisible();
    await expect(page.getByText('Enterprise Quality Score').locator('..').locator('dd')).toHaveText('—');
    await page.getByRole('button', { name: 'Clear filters' }).click();
    await page.getByRole('link', { name: 'My profile' }).click();
    await page.getByLabel('Default landing page').selectOption('dashboard');
    await page.getByRole('button', { name: 'Save preference' }).click();
    await expect(page.getByRole('status')).toHaveText('Preference saved.');
    await page.getByRole('button', { name: 'Sign out' }).click();
    await page.getByLabel('Email address').fill('admin@ketsip.local');
    await page.getByLabel('Password').fill(password);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page.getByRole('heading', { name: 'Executive Dashboard' })).toBeVisible();
    await page.goto('/');
    await expect(page).toHaveURL(/\/dashboard$/);
  } finally {
    const currentToken = await page.evaluate(() => sessionStorage.getItem('ketsip-token'));
    const currentHeaders = { Authorization: `Bearer ${currentToken || token}` };
    const restore = await page.request.put('/api/profile', { headers: currentHeaders, data: { defaultLandingPage: previousLanding } });
    expect(restore.ok()).toBeTruthy();
    const deleted = await page.request.delete(`/api/portfolios/${portfolio.id}`, { headers: currentHeaders });
    expect(deleted.status()).toBe(204);
  }
  expect(errors).toEqual([]);
});
