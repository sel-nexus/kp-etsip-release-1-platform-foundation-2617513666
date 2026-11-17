import { expect, test } from '@playwright/test';

test('real identity journey persists profile and captures browser errors', async ({ page }) => {
  const password = process.env.E2E_PASSWORD;
  if (!password) throw new Error('Set E2E_PASSWORD to the configured demo bootstrap password');
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  await page.goto('/');
  await page.getByLabel('Email address').fill('admin@ketsip.local');
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.getByRole('link', { name: 'My profile' }).click();
  await expect(page.getByRole('heading', { name: 'My profile' })).toBeVisible();
  await expect(page.getByText('admin@ketsip.local')).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem('ketsip-token'));
  const me = await page.request.get('/api/auth/me', { headers: { Authorization: `Bearer ${token}` } });
  expect(me.ok()).toBeTruthy();
  const previousLanding = (await me.json()).defaultLandingPage;
  try {
    await page.getByLabel('Current password').fill(password);
    await page.getByLabel('New password', { exact: true }).fill('new-password-1234');
    await page.getByLabel('Confirm new password').fill('different-password-1234');
    await page.getByRole('button', { name: 'Change password' }).click();
    await expect(page.getByRole('alert')).toHaveText('New passwords do not match.');
    await page.getByLabel('Default landing page').selectOption('applications');
    await page.getByRole('button', { name: 'Save preference' }).click();
    await expect(page.getByRole('status')).toHaveText('Preference saved.');
    await page.reload();
    await expect(page.getByLabel('Default landing page')).toHaveValue('applications');
    await page.getByRole('button', { name: 'Sign out' }).click();
    await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible();
  } finally {
    const login = await page.request.post('/api/auth/login', { data: { email: 'admin@ketsip.local', password } });
    expect(login.ok()).toBeTruthy();
    const restore = await page.request.put('/api/profile', { headers: { Authorization: `Bearer ${(await login.json()).token}` }, data: { defaultLandingPage: previousLanding } });
    expect(restore.ok()).toBeTruthy();
  }
  expect(errors).toEqual([]);
});
