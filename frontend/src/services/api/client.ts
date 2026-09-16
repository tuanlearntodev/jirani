// src/services/api/client.ts
import API_BASE from '../../config';

interface AuthShape {
    access_token: string;
}

function getToken(): string | null {
    try {
        const raw = localStorage.getItem('auth');
        if (!raw) return null;
        const parsed = JSON.parse(raw) as AuthShape;
        return parsed.access_token ?? null;
    } catch {
        return null;
    }
}

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
    const token = getToken();
    const headers = new Headers(init.headers);
    if (token) headers.set('Authorization', `Bearer ${token}`);

    const res = await fetch(`${API_BASE}${path}`, { ...init, headers, credentials: 'include' });

    if (res.status === 401) {
        localStorage.removeItem('auth');
    }
    return res;
}

export async function parseErrorDetail(res: Response, fallback: string): Promise<string> {
    try {
        const d = await res.json();
        return d?.detail ?? fallback;
    } catch {
        return fallback;
    }
}