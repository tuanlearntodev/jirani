// src/types.ts
export interface Tag {
    id: number | string;
    name: string;
}

export interface Book {
    uid: string;
    title: string;
    extension: string;
    cover_url?: string | null;
    author?: string | null;
    level?: string | null;
    genre?: string | null;
    language?: string | null;
    tags?: Tag[];
}

export interface Video {
    id: number | string;
    title: string;
    description?: string | null;
    tags?: Tag[];
}

export interface Audio {
    id: number | string;
    title: string;
    description?: string | null;
    audio_url?: string;
    tags?: Tag[];
}

export interface Page<T> {
    items: T[];
    total: number;
    limit: number;
    offset: number;
}

export type Role = "admin" | "teacher" | "student";

export interface LoginResponse {
    access_token: string;
    token_type: string;
    username: string;
    role: Role;
    first_login: boolean;
}