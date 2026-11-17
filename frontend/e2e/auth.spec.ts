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
  await page.getByLabel('Current password').fill(password);
  await page.getByLabel('New password').fill('new-password-1234');
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
  expect(errors).toEqual([]);
});
