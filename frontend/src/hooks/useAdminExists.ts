import { useState, useEffect } from 'react';
import { checkAdminExists } from '../services/api/auth';

export function useAdminExists() {
    const [adminExists, setAdminExists] = useState<boolean | null>(null);

    useEffect(() => {
        checkAdminExists()
            .then(setAdminExists)
            .catch(() => setAdminExists(false));
    }, []);

    return { adminExists, setAdminExists };
}