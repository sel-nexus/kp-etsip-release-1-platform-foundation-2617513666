import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom/vitest';
import Login from './Login';
import Profile from './Profile';
import type { User } from '../types';

afterEach(() => { cleanup(); vi.restoreAllMocks(); });
const user: User = { id: '1', name: 'Demo Administrator', email: 'admin@ketsip.local', role: 'Administrator', portfolioAccess: [], status: 'Active', defaultLandingPage: 'dashboard', permissions: ['view'] };

describe('identity forms', () => {
  it('submits the entered credentials', async () => {
    const onLogin = vi.fn().mockResolvedValue(undefined);
    render(<Login onLogin={onLogin} />);
    await userEvent.type(screen.getByLabelText('Email address'), 'admin@ketsip.local');
    await userEvent.type(screen.getByLabelText('Password'), 'a-long-password');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(onLogin).toHaveBeenCalledWith('admin@ketsip.local', 'a-long-password');
  });
  it('presents authentication errors', async () => {
    render(<Login onLogin={vi.fn().mockRejectedValue(new Error('Invalid email or password'))} />);
    await userEvent.type(screen.getByLabelText('Email address'), 'admin@ketsip.local');
    await userEvent.type(screen.getByLabelText('Password'), 'wrong');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid email or password');
  });
  it('saves a preference and rejects mismatched passwords', async () => {
    const updated = { ...user, defaultLandingPage: 'applications' };
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify(updated), { status: 200 }));
    const onUser = vi.fn();
    render(<Profile user={user} onUser={onUser} onSessionEnd={vi.fn()} />);
    await userEvent.selectOptions(screen.getByLabelText('Default landing page'), 'applications');
    await userEvent.click(screen.getByRole('button', { name: 'Save preference' }));
    expect(await screen.findByRole('status')).toHaveTextContent('Preference saved');
    expect(onUser).toHaveBeenCalledWith(updated);
    await userEvent.type(screen.getByLabelText('Current password'), 'old-password-123');
    await userEvent.type(screen.getByLabelText('New password'), 'new-password-123');
    await userEvent.type(screen.getByLabelText('Confirm new password'), 'different-password-123');
    await userEvent.click(screen.getByRole('button', { name: 'Change password' }));
    expect(screen.getByRole('alert')).toHaveTextContent('do not match');
  });
});
