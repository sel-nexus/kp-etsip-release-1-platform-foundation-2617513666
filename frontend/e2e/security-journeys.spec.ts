import { expect, test } from '@playwright/test';
import { randomUUID } from 'node:crypto';

test('fresh session is challenged on a protected route', async ({ page }) => {
  const errors: string[] = [];
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/administration');
  await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Account navigation' })).toHaveCount(0);
  expect((await page.request.get('/api/users')).status()).toBe(401);
  expect(errors).toEqual([]);
});

test('restricted user changes password and signs in again without gaining administration access', async ({ page }) => {
  const password = process.env.E2E_PASSWORD;
  if (!password) throw new Error('Set E2E_PASSWORD to the configured demo bootstrap password');
  const errors: string[] = [];
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('pageerror', error => errors.push(error.message));
  const adminLogin = await page.request.post('/api/auth/login', { data: { email: 'admin@ketsip.local', password } });
  expect(adminLogin.ok()).toBeTruthy();
  const headers = { Authorization: `Bearer ${(await adminLogin.json()).token}` };
  const rolesResponse = await page.request.get('/api/roles?limit=100', { headers });
  expect(rolesResponse.ok()).toBeTruthy();
  const roles: { name: string; permissions: string[] }[] = (await rolesResponse.json()).items;
  const role = roles.find(item => item.name === 'Read Only' && item.permissions.includes('view'))
    || roles.find(item => item.name !== 'Administrator' && item.permissions.includes('view'));
  if (!role) throw new Error('A configured non-administrator role with view permission is required');
  const email = `e2e-security-${randomUUID()}@example.com`;
  const originalPassword = 'Test-original-password-1234';
  const newPassword = 'Test-replacement-password-5678';
  const created = await page.request.post('/api/users', { headers, data: { name: 'E2E security account', email, password: originalPassword, role: role.name, status: 'Active', portfolioAccess: [] } });
  expect(created.status()).toBe(201);
  const user = await created.json();
  try {
    await page.goto('/administration');
    await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible();
    await page.getByLabel('Email address').fill(email);
    await page.getByLabel('Password').fill(originalPassword);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page.getByRole('link', { name: 'My profile' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Administration' })).toHaveCount(0);
    const oldToken = await page.evaluate(() => sessionStorage.getItem('ketsip-token'));
    expect(oldToken).toBeTruthy();
    expect((await page.request.get('/api/users', { headers: { Authorization: `Bearer ${oldToken}` } })).status()).toBe(403);
    await page.getByRole('link', { name: 'My profile' }).click();
    await expect(page.getByText(email)).toBeVisible();
    await page.getByLabel('Current password').fill(originalPassword);
    await page.getByLabel('New password', { exact: true }).fill(newPassword);
    await page.getByLabel('Confirm new password').fill(newPassword);
    await page.getByRole('button', { name: 'Change password' }).click();
    await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible();
    expect((await page.request.get('/api/auth/me', { headers: { Authorization: `Bearer ${oldToken}` } })).status()).toBe(401);
    expect((await page.request.post('/api/auth/login', { data: { email, password: originalPassword } })).status()).toBe(401);
    await page.getByLabel('Email address').fill(email);
    await page.getByLabel('Password').fill(newPassword);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await page.getByRole('link', { name: 'My profile' }).click();
    await expect(page.getByText(email)).toBeVisible();
    await expect(page.getByText(role.name, { exact: true })).toBeVisible();
  } finally {
    expect((await page.request.delete(`/api/users/${user.id}`, { headers })).status()).toBe(204);
  }
  expect(errors).toEqual([]);
});

test('restricted user cannot enter the administration route', async ({ page }) => {
  const password = process.env.E2E_PASSWORD;
  if (!password) throw new Error('Set E2E_PASSWORD to the configured demo bootstrap password');
  const errors: string[] = [];
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('pageerror', error => errors.push(error.message));
  const adminLogin = await page.request.post('/api/auth/login', { data: { email: 'admin@ketsip.local', password } });
  expect(adminLogin.ok()).toBeTruthy();
  const headers = { Authorization: `Bearer ${(await adminLogin.json()).token}` };
  const rolesResponse = await page.request.get('/api/roles?limit=100', { headers });
  expect(rolesResponse.ok()).toBeTruthy();
  const roles: { name: string; permissions: string[] }[] = (await rolesResponse.json()).items;
  const role = roles.find(item => item.name === 'Read Only' && item.permissions.includes('view'))
    || roles.find(item => item.name !== 'Administrator' && item.permissions.includes('view'));
  if (!role) throw new Error('A configured non-administrator role with view permission is required');
  const email = `e2e-route-${randomUUID()}@example.com`;
  const userPassword = 'Test-route-password-1234';
  const created = await page.request.post('/api/users', { headers, data: { name: 'E2E route account', email, password: userPassword, role: role.name, status: 'Active', portfolioAccess: [] } });
  expect(created.status()).toBe(201);
  const user = await created.json();
  try {
    const login = await page.request.post('/api/auth/login', { data: { email, password: userPassword } });
    expect(login.ok()).toBeTruthy();
    const token: string = (await login.json()).token;
    expect((await page.request.get('/api/users', { headers: { Authorization: `Bearer ${token}` } })).status()).toBe(403);
    await page.addInitScript(token => sessionStorage.setItem('ketsip-token', token), token);
    await page.goto('/administration');
    await expect(page.getByRole('alert')).toHaveText('You do not have access to administration.');
    await expect(page.getByRole('link', { name: 'Administration' })).toHaveCount(0);
    await expect(page.getByRole('link', { name: 'My profile' })).toBeVisible();
  } finally {
    expect((await page.request.delete(`/api/users/${user.id}`, { headers })).status()).toBe(204);
  }
  expect(errors).toEqual([]);
});

test('application detail renders stored HTML as text without executing it', async ({ page }) => {
  const password = process.env.E2E_PASSWORD;
  if (!password) throw new Error('Set E2E_PASSWORD to the configured demo bootstrap password');
  const errors: string[] = [];
  const dialogs: string[] = [];
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('pageerror', error => errors.push(error.message));
  page.on('dialog', dialog => { dialogs.push(dialog.message()); void dialog.dismiss(); });
  const login = await page.request.post('/api/auth/login', { data: { email: 'admin@ketsip.local', password } });
  expect(login.ok()).toBeTruthy();
  const headers = { Authorization: `Bearer ${(await login.json()).token}` };
  const name = `XSS application ${randomUUID()}`;
  const payload = '<script id="e2e-xss-script">window.__e2eXssExecuted=true;alert("stored-xss")</script><img id="e2e-xss-image" src="x" onerror="window.__e2eXssExecuted=true;alert(\'stored-xss\')">';
  const portfolio = await page.request.post('/api/portfolios', { headers, data: { name: `XSS portfolio ${randomUUID()}` } });
  expect(portfolio.status()).toBe(201);
  const portfolioId: string = (await portfolio.json()).id;
  let applicationId: string | undefined;
  try {
    const created = await page.request.post('/api/applications', { headers, data: { name, portfolioId, description: payload } });
    expect(created.status()).toBe(201);
    const application = await created.json();
    applicationId = application.id;
    expect(application.description).toBe(payload);
    await page.goto('/');
    await page.getByLabel('Email address').fill('admin@ketsip.local');
    await page.getByLabel('Password').fill(password);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await page.getByRole('link', { name: 'Applications', exact: true }).click();
    await page.getByLabel('Search').fill(name);
    await page.getByRole('link', { name, exact: true }).click();
    await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
    const description = page.locator('dt', { hasText: 'Description' }).locator('..').locator('dd');
    await expect(description).toBeVisible();
    await expect(description).toHaveText(payload);
    await expect(page.locator('#e2e-xss-script, #e2e-xss-image')).toHaveCount(0);
    expect(await page.evaluate(() => (window as Window & { __e2eXssExecuted?: boolean }).__e2eXssExecuted)).toBeUndefined();
    expect(dialogs).toEqual([]);
  } finally {
    try {
      if (applicationId) expect((await page.request.delete(`/api/applications/${applicationId}`, { headers })).status()).toBe(204);
    } finally {
      expect((await page.request.delete(`/api/portfolios/${portfolioId}`, { headers })).status()).toBe(204);
    }
  }
  expect(errors).toEqual([]);
});

test('administrator edits a configured role permission and restores it', async ({ page }) => {
  const password = process.env.E2E_PASSWORD;
  if (!password) throw new Error('Set E2E_PASSWORD to the configured demo bootstrap password');
  const errors: string[] = [];
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await page.getByLabel('Email address').fill('admin@ketsip.local');
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.getByRole('link', { name: 'Administration' }).click();
  const token = await page.evaluate(() => sessionStorage.getItem('ketsip-token'));
  const headers = { Authorization: `Bearer ${token}` };
  const response = await page.request.get('/api/roles?limit=100', { headers });
  expect(response.ok()).toBeTruthy();
  const roles: { id: string; name: string; description: string; permissions: string[] }[] = (await response.json()).items;
  const role = roles.find(item => item.name === 'Read Only') || roles.find(item => item.name === 'Auditor') || roles.find(item => item.name !== 'Administrator');
  if (!role) throw new Error('A configured non-administrator role is required');
  const permissions = role.permissions.includes('export') ? role.permissions.filter(item => item !== 'export') : [...role.permissions, 'export'];
  try {
    await page.getByRole('button', { name: 'Roles', exact: true }).click();
    await page.getByRole('button', { name: `Edit ${role.name}`, exact: true }).click();
    await page.getByRole('checkbox', { name: 'export', exact: true }).setChecked(permissions.includes('export'));
    const saved = page.waitForResponse(res => res.url().endsWith(`/api/roles/${role.id}`) && res.request().method() === 'PUT');
    await page.getByRole('button', { name: 'Save role' }).click();
    expect((await saved).ok()).toBeTruthy();
    await expect(page.getByRole('button', { name: `Edit ${role.name}`, exact: true })).toBeVisible();
    const updated = await page.request.get('/api/roles?limit=100', { headers });
    expect(updated.ok()).toBeTruthy();
    expect((await updated.json()).items.find((item: { id: string }) => item.id === role.id).permissions.sort()).toEqual([...permissions].sort());
    await page.getByRole('button', { name: `Edit ${role.name}`, exact: true }).click();
    await expect(page.getByRole('checkbox', { name: 'export', exact: true })).toBeChecked({ checked: permissions.includes('export') });
  } finally {
    const restored = await page.request.put(`/api/roles/${role.id}`, { headers, data: { name: role.name, description: role.description, permissions: role.permissions } });
    expect(restored.ok()).toBeTruthy();
  }
  expect(errors).toEqual([]);
});
