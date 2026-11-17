import { expect, test } from '@playwright/test';

test('restored session entering at root follows the saved dashboard preference', async ({ page }) => {
  const password = process.env.E2E_PASSWORD;
  if (!password) throw new Error('Set E2E_PASSWORD to the configured demo bootstrap password');
  const errors: string[] = [];
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('pageerror', error => errors.push(error.message));
  const login = await page.request.post('/api/auth/login', { data: { email: 'admin@ketsip.local', password } });
  expect(login.ok()).toBeTruthy();
  const token = (await login.json()).token;
  const headers = { Authorization: `Bearer ${token}` };
  const me = await page.request.get('/api/auth/me', { headers });
  expect(me.ok()).toBeTruthy();
  const previousLanding = (await me.json()).defaultLandingPage;
  try {
    expect((await page.request.put('/api/profile', { headers, data: { defaultLandingPage: 'dashboard' } })).ok()).toBeTruthy();
    await page.addInitScript(value => sessionStorage.setItem('ketsip-token', value), token);
    await page.goto('/');
    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByRole('heading', { name: 'Executive Dashboard' })).toBeVisible();
    await expect(page.getByText('Total Applications', { exact: true })).toBeVisible();
  } finally {
    expect((await page.request.put('/api/profile', { headers, data: { defaultLandingPage: previousLanding } })).ok()).toBeTruthy();
  }
  expect(errors).toEqual([]);
});

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
    // Enter from another view so the dashboard refetches the newly created data.
    await page.getByRole('link', { name: 'My profile' }).click();
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
    await expect(page).toHaveURL(/\/dashboard$/);
  } finally {
    const login = await page.request.post('/api/auth/login', { data: { email: 'admin@ketsip.local', password } });
    expect(login.ok()).toBeTruthy();
    const currentHeaders = { Authorization: `Bearer ${(await login.json()).token}` };
    const restore = await page.request.put('/api/profile', { headers: currentHeaders, data: { defaultLandingPage: previousLanding } });
    const deleted = await page.request.delete(`/api/portfolios/${portfolio.id}`, { headers: currentHeaders });
    expect(restore.ok()).toBeTruthy();
    expect(deleted.status()).toBe(204);
  }
  expect(errors).toEqual([]);
});
