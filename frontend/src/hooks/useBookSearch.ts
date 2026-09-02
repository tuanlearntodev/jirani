import { useState, useEffect, useCallback } from 'react';
import { Book } from '../types';
import * as booksApi from '../api/books';

export function useBookSearch(tags: string[], title: string) {
    const [books, setBooks] = useState<Book[]>([]);
    const tagsKey = tags.join(',');

    const refresh = useCallback(async () => {
        setBooks(await booksApi.searchBooks({ tags, title }));
        // tagsKey is the stable representation of `tags` used for comparison
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [tagsKey, title]);

    useEffect(() => { refresh(); }, [refresh]);

    return { books, refresh, setBooks };
}