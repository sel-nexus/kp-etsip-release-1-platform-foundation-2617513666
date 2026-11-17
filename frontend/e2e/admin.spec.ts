import { expect, test } from '@playwright/test';
import { randomUUID } from 'node:crypto';

test('administrator manages a user and reviews the audit trail', async ({ page }) => {
  const password = process.env.E2E_PASSWORD;
  if (!password) throw new Error('Set E2E_PASSWORD to the configured demo bootstrap password');
  const errors: string[] = [];
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('pageerror', error => errors.push(error.message));
  const suffix = randomUUID();
  const name = `Journey user ${suffix}`;
  const email = `journey-${suffix}@example.com`;
  await page.goto('/');
  await page.getByLabel('Email address').fill('admin@ketsip.local');
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.getByRole('link', { name: 'Administration' }).click();
  const token = await page.evaluate(() => sessionStorage.getItem('ketsip-token'));
  expect(token).toBeTruthy();
  const headers = { Authorization: `Bearer ${token}` };
  try {
    await page.getByRole('button', { name: 'Create user' }).click();
    await page.getByLabel('Name', { exact: true }).fill(name);
    await page.getByLabel('Email address').fill(email);
    await page.getByLabel('Password').fill('Journey-password-1234');
    const roleOptions = await page.getByLabel('Role').locator('option').allTextContents();
    const role = roleOptions.find(option => option === 'Engineer') || roleOptions.find(option => option !== 'Administrator');
    if (!role) throw new Error('A configured non-administrator role is required for this journey');
    await page.getByLabel('Role').selectOption({ label: role });
    await page.getByRole('button', { name: 'Save user' }).click();
    await expect(page.getByRole('cell', { name })).toBeVisible();
    await page.getByRole('button', { name: `Edit ${name}` }).click();
    await page.getByLabel('Status').selectOption('Inactive');
    await page.getByRole('button', { name: 'Save user' }).click();
    await expect(page.getByRole('row').filter({ hasText: email })).toContainText('Inactive');
    page.once('dialog', dialog => dialog.accept());
    await page.getByRole('button', { name: `Delete ${name}` }).click();
    await expect(page.getByRole('cell', { name })).toHaveCount(0);
    await page.getByRole('button', { name: 'Audit' }).click();
    await page.getByLabel('Action').fill('delete');
    await expect(page.getByText('User delete').first()).toBeVisible();
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Export CSV' }).click();
    expect((await downloadPromise).suggestedFilename()).toBe('audit-logs.csv');
  } finally {
    // Find the unique account even if the UI failed after the create request.
    let offset = 0;
    while (true) {
      const response = await page.request.get(`/api/users?limit=100&offset=${offset}`, { headers });
      expect(response.ok()).toBeTruthy();
      const users: { items: { id: string; email: string }[]; total: number } = await response.json();
      const user = users.items.find(item => item.email === email);
      if (user) {
        expect((await page.request.delete(`/api/users/${user.id}`, { headers })).status()).toBe(204);
        break;
      }
      offset += users.items.length;
      if (!users.items.length || offset >= users.total) break;
    }
  }
  expect(errors).toEqual([]);
});
