import * as pdfjsLib from 'pdfjs-dist';
import { apiFetch, parseErrorDetail } from './client';
import { Book, Page } from '../../types';

pdfjsLib.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.mjs';

const BASE = '/books';

export function getBookStreamUrl(uid: Book['uid']): string {
    return `${BASE}/${uid}/stream`;
}
export function getBookReadUrl(uid: Book['uid']): string {
    return `${BASE}/${uid}/read`;
}

export interface BookSearchParams {
    title?: string;
    author?: string;
    level?: string;
    genre?: string;
    language?: string;
    tags?: string[];
    extension?: string;
    limit?: number;
    offset?: number;
}

export async function searchBooks(params: BookSearchParams = {}): Promise<Page<Book>> {
    const query = new URLSearchParams();
    if (params.title?.trim()) query.set('title', params.title.trim());
    if (params.author?.trim()) query.set('author', params.author.trim());
    if (params.level?.trim()) query.set('level', params.level.trim());
    if (params.genre?.trim()) query.set('genre', params.genre.trim());
    if (params.language?.trim()) query.set('language', params.language.trim());
    if (params.extension?.trim()) query.set('extension', params.extension.trim());
    if (params.tags && params.tags.length > 0) query.set('tags', params.tags.join(','));
    query.set('limit', String(params.limit ?? 100));
    query.set('offset', String(params.offset ?? 0));

    const res = await apiFetch(`${BASE}/?${query}`);
    if (!res.ok) throw new Error('Failed to fetch books');
    return res.json();
}

export async function uploadBook(
    file: File,
    meta: { title?: string; author?: string; level?: string; genre?: string; language?: string; tags?: string } = {},
): Promise<Book> {
    const formData = new FormData();
    formData.append('file', file);
    if (meta.title?.trim()) formData.append('title', meta.title.trim());
    if (meta.author?.trim()) formData.append('author', meta.author.trim());
    if (meta.level?.trim()) formData.append('level', meta.level.trim());
    if (meta.genre?.trim()) formData.append('genre', meta.genre.trim());
    if (meta.language?.trim()) formData.append('language', meta.language.trim());
    if (meta.tags?.trim()) formData.append('tags', meta.tags.trim());

    const res = await apiFetch(`${BASE}/upload`, { method: 'POST', body: formData });
    if (!res.ok) throw new Error(await parseErrorDetail(res, 'Upload failed'));
    return res.json();
}

export async function uploadBooks(
    files: File[],
    meta: { tags?: string } = {},
): Promise<Book[]> {
    const results: Book[] = [];
    for (const file of files) {
        results.push(await uploadBook(file, meta));
    }
    return results;
}

export async function deleteBook(uid: Book['uid']): Promise<void> {
    const res = await apiFetch(`${BASE}/${uid}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Delete failed');
}

export async function updateBook(
    uid: Book['uid'],
    fields: { title?: string; author?: string; level?: string; genre?: string; language?: string; tags?: string; cover?: File },
): Promise<Book> {
    const formData = new FormData();
    if (fields.title?.trim()) formData.append('title', fields.title.trim());
    if (fields.author?.trim()) formData.append('author', fields.author.trim());
    if (fields.level?.trim()) formData.append('level', fields.level.trim());
    if (fields.genre?.trim()) formData.append('genre', fields.genre.trim());
    if (fields.language?.trim()) formData.append('language', fields.language.trim());
    if (fields.tags !== undefined) formData.append('tags', fields.tags.trim());
    if (fields.cover) formData.append('cover', fields.cover);

    const res = await apiFetch(`${BASE}/${uid}`, { method: 'PUT', body: formData });
    if (!res.ok) throw new Error(await parseErrorDetail(res, 'Update failed'));
    return res.json();
}