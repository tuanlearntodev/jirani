// src/hooks/useBookSearch.ts
import { useState, useEffect, useCallback } from 'react';
import { Book } from '../types';
import * as booksApi from '../services/api/books';

export function useBookSearch(tags: string[], title: string) {
    const [books, setBooks] = useState<Book[]>([]);
    const [total, setTotal] = useState(0);
    const tagsKey = tags.join(',');

    const refresh = useCallback(async () => {
        const page = await booksApi.searchBooks({ tags, title });
        setBooks(page.items);
        setTotal(page.total);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [tagsKey, title]);

    useEffect(() => { refresh(); }, [refresh]);

    return { books, total, refresh, setBooks };
}