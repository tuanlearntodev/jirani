// src/services/api/setup.ts
import { apiFetch, parseErrorDetail } from './client';

export interface SetupResponse {
    message: string;
}

// GET /setup — one-time admin bootstrap. Succeeds once, then permanently
// 403s on every call after (backend sets a REVEALED_FLAG on disk).
export async function runSetup(): Promise<SetupResponse> {
    const res = await apiFetch('/setup', { method: 'GET' });
    if (!res.ok) throw new Error(await parseErrorDetail(res, 'Setup failed.'));
    return res.json();
}