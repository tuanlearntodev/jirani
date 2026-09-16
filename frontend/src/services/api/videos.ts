// src/services/api/videos.ts
import { apiFetch, parseErrorDetail } from './client';
import { Video } from '../../types';
import API_BASE from '../../config';

const BASE = '/videos';

export function getVideoStreamUrl(id: Video['id']): string {
    return `${API_BASE}${BASE}/stream/${id}`;
}

export async function fetchVideos(): Promise<Video[]> {
    const res = await apiFetch(`${BASE}/`);
    if (!res.ok) throw new Error('Failed to fetch videos');
    return res.json();
}

export async function uploadVideo(file: File, tags?: string): Promise<Video> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', file.name.replace(/\.[^/.]+$/, ''));
    if (tags?.trim()) formData.append('tags', tags.trim());
    const res = await apiFetch(`${BASE}/upload`, { method: 'POST', body: formData });
    if (!res.ok) throw new Error(await parseErrorDetail(res, 'Upload failed'));
    return res.json();
}

export async function uploadVideos(files: File[]): Promise<Video[]> {
    const formData = new FormData();
    files.forEach(f => formData.append('files', f));
    const res = await apiFetch(`${BASE}/upload_multiple`, { method: 'POST', body: formData });
    if (!res.ok) throw new Error(await parseErrorDetail(res, 'Upload failed'));
    return res.json();
}

export async function deleteVideo(id: Video['id']): Promise<void> {
    const res = await apiFetch(`${BASE}/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Delete failed');
}

export async function updateVideo(
    id: Video['id'], title: string, description: string, tags: string = '',
): Promise<Video> {
    const params = new URLSearchParams();
    if (title.trim()) params.append('title', title.trim());
    params.append('description', description);
    params.append('tags', tags);
    const res = await apiFetch(`${BASE}/${id}?${params}`, { method: 'PATCH' });
    if (!res.ok) throw new Error(await parseErrorDetail(res, 'Update failed'));
    return res.json();
}