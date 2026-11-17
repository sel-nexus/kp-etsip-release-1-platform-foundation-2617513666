import { expect, test } from '@playwright/test';

test('dashboard shows loading until the real metrics request completes', async ({ page }) => {
  const password = process.env.E2E_PASSWORD;
  if (!password) throw new Error('Set E2E_PASSWORD to the configured demo bootstrap password');
  const errors: string[] = [];
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('pageerror', error => errors.push(error.message));
  let release!: () => void;
  const hold = new Promise<void>(resolve => { release = resolve; });
  await page.route('**/api/dashboard/executive**', async route => {
    await hold;
    await route.continue();
  });
  try {
    await page.goto('/');
    await page.getByLabel('Email address').fill('admin@ketsip.local');
    await page.getByLabel('Password').fill(password);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page.getByRole('link', { name: 'Dashboard', exact: true })).toBeVisible();
    if (!new URL(page.url()).pathname.startsWith('/dashboard')) {
      await page.getByRole('link', { name: 'Dashboard', exact: true }).click();
    }
    await expect(page.getByRole('status')).toHaveText('Loading dashboard…');
    const response = page.waitForResponse(res => res.url().includes('/api/dashboard/executive') && res.request().method() === 'GET');
    release();
    const metrics = await response;
    expect(metrics.ok()).toBeTruthy();
    const data = await metrics.json();
    await expect(page.getByText('Total Applications', { exact: true }).locator('..').locator('dd')).toHaveText(String(data.totalApplications));
    await expect(page.getByText('Loading dashboard…')).toHaveCount(0);
  } finally {
    release();
    await page.unrouteAll({ behavior: 'wait' });
  }
  expect(errors).toEqual([]);
});

test('desktop and mobile navigation reaches live inventory', async ({ page }, testInfo) => {
  const password = process.env.E2E_PASSWORD;
  if (!password) throw new Error('Set E2E_PASSWORD to the configured demo bootstrap password');
  const errors: string[] = [];
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('pageerror', error => errors.push(error.message));
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/');
  await page.getByLabel('Email address').fill('admin@ketsip.local');
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.getByRole('link', { name: 'Dashboard', exact: true }).click();
  await expect(page.getByText('Total Applications', { exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('dashboard-desktop.png'), fullPage: true });
  await page.setViewportSize({ width: 375, height: 812 });
  const navigation = page.getByRole('navigation', { name: 'Account navigation' });
  await expect(navigation.getByRole('link', { name: 'Applications', exact: true })).toBeVisible();
  const response = page.waitForResponse(res => new URL(res.url()).pathname === '/api/applications' && res.request().method() === 'GET');
  await navigation.getByRole('link', { name: 'Applications', exact: true }).click();
  const inventory = await response;
  expect(inventory.ok()).toBeTruthy();
  const data = await inventory.json();
  await expect(page.getByRole('heading', { name: 'Application repository' })).toBeVisible();
  await expect(page.getByText(`${data.total} total`, { exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('applications-mobile.png'), fullPage: true });
  expect(errors).toEqual([]);
});
