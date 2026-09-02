import API_BASE from '../../config';
import { LoginResponse, SignupData } from '../../types';

const BASE = `${API_BASE}/auth`;

export async function checkAdminExists(): Promise<boolean> {
    const res = await fetch(`${BASE}/admin-exists`);
    const data: { exists: boolean } = await res.json();
    return data.exists;
}

export async function login(username: string, password: string): Promise<LoginResponse> {
    const res = await fetch(`${BASE}/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
        const d = await res.json().catch(() => null);
        throw new Error(d?.detail ?? 'Invalid username or password.');
    }
    return res.json();
}

export async function verifyResetCode(username: string, otp: string, newPassword: string): Promise<void> {
    const params = new URLSearchParams({ username, otp, new_password: newPassword });
    const res = await fetch(`${BASE}/forgot-password/verify-code?${params}`, { method: 'POST' });
    if (!res.ok) {
        const d = await res.json();
        throw new Error(d.detail);
    }
}

export async function signup(data: SignupData): Promise<{ recovery_code: string }> {
    const res = await fetch(`${BASE}/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
    if (!res.ok) {
        const d = await res.json().catch(() => null);
        throw new Error(d?.detail ?? 'Signup failed.');
    }
    return res.json();
}

export async function makeAdmin(username: string): Promise<void> {
    await fetch(`${BASE}/make-admin/${username}`, { method: 'POST' });
}