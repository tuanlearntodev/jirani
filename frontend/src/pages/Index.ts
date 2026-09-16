export interface Tag {
    id: number | string;
    name: string;
}

export interface Book {
    uid: string;
    title: string;
    extension: string;
    cover_url?: string | null;
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
    tags?: Tag[];
}

export interface AuthUser {
    username: string;
    [key: string]: unknown;
}

export interface LoginResponse {
    access_token: string;
    token_type: string;
    username?: string;
    is_admin?: boolean;
    [key: string]: unknown;
}

export interface AuthContextValue {
    auth: AuthUser | null;
    isAdmin: boolean;
    login: (data: LoginResponse) => void;
    logout: () => void;
}

export interface SignupData {
    username: string;
    password: string;
    first_name: string;
    last_name: string;
}

export interface UploadType {
    tab: "book" | "audio" | "video";
}