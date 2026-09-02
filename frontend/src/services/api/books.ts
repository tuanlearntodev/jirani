import * as pdfjsLib from 'pdfjs-dist';
import API_BASE from '../../config';
import { Book } from '../../types';

// PDF.js needs its worker script configured once, globally.
// Living here keeps that setup out of the component/hook layer.
pdfjsLib.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.mjs';

const BASE = `${API_BASE}/books`;

export function getBookReadUrl(uid: Book['uid']): string {
    return `${BASE}/${uid}/read`;
}

export interface BookSearchParams {
    tags?: string[];
    title?: string;
}

// Backend search endpoint, e.g. GET /books/search/?tags=a,b&title=foo
// Calling with no params returns the full list — this is also what
// the plain "list all books" case uses.
export async function searchBooks(params: BookSearchParams = {}): Promise<Book[]> {
    const query = new URLSearchParams();
    if (params.tags && params.tags.length > 0) query.set('tags', params.tags.join(','));
    if (params.title?.trim()) query.set('title', params.title.trim());
    const res = await fetch(`${BASE}/search/?${query}`);
    if (!res.ok) throw new Error('Failed to search books');
    return res.json();
}

export async function fetchBooks(): Promise<Book[]> {
    return searchBooks();
}

export async function uploadBook(file: File, tags?: string): Promise<void> {
    const formData = new FormData();
    formData.append('file', file);
    if (tags?.trim()) formData.append('tags', tags.trim());
    const res = await fetch(`${BASE}/upload`, { method: 'POST', body: formData });
    if (!res.ok) {
        const d = await res.json().catch(() => null);
        throw new Error(d?.detail ?? 'Upload failed');
    }
}

export async function uploadBooks(files: File[], tags?: string): Promise<void> {
    // Backend book upload only documents a single-file /upload route today —
    // loop it for multi-file, matching how Library.tsx's UploadModal does books.
    for (const file of files) {
        await uploadBook(file, tags);
    }
}

export async function deleteBook(uid: Book['uid']): Promise<void> {
    const res = await fetch(`${BASE}/${uid}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Delete failed');
}

export async function updateBook(uid: Book['uid'], title: string, tags: string = ''): Promise<Book> {
    const formData = new FormData();
    if (title.trim()) formData.append('title', title.trim());
    formData.append('tags', tags.trim());
    const res = await fetch(`${BASE}/${uid}`, { method: 'PUT', body: formData });
    if (!res.ok) {
        const d = await res.json().catch(() => null);
        throw new Error(d?.detail ?? 'Update failed');
    }
    return res.json();
}