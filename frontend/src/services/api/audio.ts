// src/services/api/audio.ts
import { apiFetch, parseErrorDetail } from './client';
import { Audio } from '../../types';

const BASE = '/audio';

export function getAudioStreamUrl(id: Audio['id']): string {
    return `${BASE}/stream/${id}`;
}

export async function fetchAudioTracks(): Promise<Audio[]> {
    const res = await apiFetch(`${BASE}/`);
    if (!res.ok) throw new Error('Failed to fetch audio');
    return res.json();
}

export async function uploadAudio(file: File, tags?: string): Promise<Audio> {
    const formData = new FormData();
    formData.append('file', file);
    if (tags?.trim()) formData.append('tags', tags.trim());
    const res = await apiFetch(`${BASE}/upload`, { method: 'POST', body: formData });
    if (!res.ok) throw new Error(await parseErrorDetail(res, 'Upload failed'));
    return res.json();
}

export async function uploadAudioTracks(files: File[]): Promise<Audio[]> {
    const formData = new FormData();
    files.forEach(f => formData.append('files', f));
    const res = await apiFetch(`${BASE}/upload_multiple`, { method: 'POST', body: formData });
    if (!res.ok) throw new Error(await parseErrorDetail(res, 'Upload failed'));
    return res.json();
}

export async function deleteAudio(id: Audio['id']): Promise<void> {
    const res = await apiFetch(`${BASE}/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Delete failed');
}

export async function updateAudio(
    id: Audio['id'], title: string, description: string, tags: string = '',
): Promise<Audio> {
    const params = new URLSearchParams();
    if (title.trim()) params.append('title', title.trim());
    params.append('description', description);
    params.append('tags', tags);
    const res = await apiFetch(`${BASE}/${id}?${params}`, { method: 'PATCH' });
    if (!res.ok) throw new Error(await parseErrorDetail(res, 'Update failed'));
    return res.json();
}