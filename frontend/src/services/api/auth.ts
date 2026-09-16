// src/services/api/auth.ts
import { apiFetch, parseErrorDetail } from './client';
import { LoginResponse, Role } from '../../types';

export async function login(username: string, password: string): Promise<LoginResponse> {
    const res = await apiFetch('/auth/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
    });
    if (!res.ok) throw new Error(await parseErrorDetail(res, 'Invalid username or password.'));
    return res.json();
}

export async function changePassword(oldPassword: string, newPassword: string): Promise<void> {
    const res = await apiFetch('/auth/change-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
    });
    if (!res.ok) throw new Error(await parseErrorDetail(res, 'Failed to change password.'));
}

export interface CreateUserRequest {
    username: string;
    first_name: string;
    last_name: string;
    role: Role;
}

export interface CreateUserResponse {
    username: string;
    credential: string;
}

// Maps to POST /auth/users. Caller must already be admin/teacher
// (enforced server-side via RoleChecker). Admin accounts cannot be
// created through this endpoint — only student/teacher.
export async function createUser(data: CreateUserRequest): Promise<CreateUserResponse> {
    const res = await apiFetch('/auth/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error(await parseErrorDetail(res, 'Failed to create account.'));
    return res.json();
}

// No backend route for OTP/forgot-password or self-signup. First-admin
// bootstrap happens once via GET /setup (server-side, not from this UI).