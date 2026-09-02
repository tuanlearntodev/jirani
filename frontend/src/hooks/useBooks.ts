import { useState, useEffect, useCallback } from 'react';
import { Book } from '../types';
import * as booksApi from '../api/books';

export function useBooks() {
    const [books, setBooks] = useState<Book[]>([]);

    const refresh = useCallback(async () => {
        setBooks(await booksApi.fetchBooks());
    }, []);

    useEffect(() => { refresh(); }, [refresh]);

    return { books, refresh, setBooks };
}