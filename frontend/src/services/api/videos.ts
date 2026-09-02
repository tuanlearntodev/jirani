import API_BASE from '../../config';
import { Video } from '../../types';

const BASE = `${API_BASE}/videos`;

export function getVideoStreamUrl(id: Video['id']): string {
    return `${BASE}/stream/${id}`;
}

export async function fetchVideos(): Promise<Video[]> {
    const res = await fetch(`${BASE}/`);
    if (!res.ok) throw new Error('Failed to fetch videos');
    return res.json();
}

export async function uploadVideo(file: File, tags?: string): Promise<void> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', file.name.replace(/\.[^/.]+$/, ''));
    if (tags?.trim()) formData.append('tags', tags.trim());
    const res = await fetch(`${BASE}/upload`, { method: 'POST', body: formData });
    if (!res.ok) {
        const d = await res.json().catch(() => null);
        throw new Error(d?.detail ?? 'Upload failed');
    }
}

export async function uploadVideos(files: File[], tags?: string): Promise<void> {
    const formData = new FormData();
    files.forEach(f => formData.append('files', f));
    if (tags?.trim()) formData.append('tags', tags.trim());
    const res = await fetch(`${BASE}/upload_multiple`, { method: 'POST', body: formData });
    if (!res.ok) {
        const d = await res.json().catch(() => null);
        throw new Error(d?.detail ?? 'Upload failed');
    }
}

export async function deleteVideo(id: Video['id']): Promise<void> {
    const res = await fetch(`${BASE}/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Delete failed');
}

export async function updateVideo(
    id: Video['id'],
    title: string,
    description: string,
    tags: string = '',
): Promise<Video> {
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