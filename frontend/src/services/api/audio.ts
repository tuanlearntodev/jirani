import API_BASE from '../../config';
import { Audio } from '../../types';

const BASE = `${API_BASE}/audio`;

export function getAudioStreamUrl(id: Audio['id']): string {
    return `${BASE}/stream/${id}`;
}

export async function fetchAudioTracks(): Promise<Audio[]> {
    const res = await fetch(`${BASE}/`);
    if (!res.ok) throw new Error('Failed to fetch audio');
    return res.json();
}

export async function uploadAudio(file: File, tags?: string): Promise<void> {
    const formData = new FormData();
    formData.append('file', file);
    if (tags?.trim()) formData.append('tags', tags.trim());
    const res = await fetch(`${BASE}/upload`, { method: 'POST', body: formData });
    if (!res.ok) {
        const d = await res.json().catch(() => null);
        throw new Error(d?.detail ?? 'Upload failed');
    }
}

export async function uploadAudioTracks(files: File[], tags?: string): Promise<void> {
    const formData = new FormData();
    files.forEach(f => formData.append('files', f));
    if (tags?.trim()) formData.append('tags', tags.trim());
    const res = await fetch(`${BASE}/upload_multiple`, { method: 'POST', body: formData });
    if (!res.ok) {
        const d = await res.json().catch(() => null);
        throw new Error(d?.detail ?? 'Upload failed');
    }
}

export async function deleteAudio(id: Audio['id']): Promise<void> {
    const res = await fetch(`${BASE}/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Delete failed');
}

export async function updateAudio(
    id: Audio['id'],
    title: string,
    description: string,
    tags: string = '',
): Promise<Audio> {
    const params = new URLSearchParams();
    if (title.trim()) params.append('title', title.trim());
    params.append('description', description);
    params.append('tags', tags);
    const res = await fetch(`${BASE}/${id}?${params}`, { method: 'PATCH' });
    if (!res.ok) {
        const d = await res.json().catch(() => null);
        throw new Error(d?.detail ?? 'Update failed');
    }
    return res.json();
}