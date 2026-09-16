// src/context/AuthContext.tsx
import { createContext, useContext, useState, ReactNode } from "react";
import { LoginResponse, Role } from "../types";

export interface AuthData {
    access_token: string;
    username: string;
    role: Role;
}

interface AuthContextType {
    auth: AuthData | null;
    login: (data: LoginResponse) => void;
    logout: () => void;
    isAdmin: boolean;
    isTeacher: boolean;
    isGuest: boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
    const [auth, setAuth] = useState<AuthData | null>(() => {
        try {
            const stored = localStorage.getItem("auth");
            return stored ? JSON.parse(stored) : null;
        } catch {
            return null;
        }
    });

    const login = (data: LoginResponse) => {
        const authData: AuthData = {
            access_token: data.access_token,
            username: data.username,
            role: data.role,
        };
        localStorage.setItem("auth", JSON.stringify(authData));
        setAuth(authData);
    };

    const logout = () => {
        localStorage.removeItem("auth");
        setAuth(null);
    };

    const isAdmin = auth?.role === "admin";
    const isTeacher = auth?.role === "teacher";
    const isGuest = !auth;

    return (
        <AuthContext.Provider value={{ auth, login, logout, isAdmin, isTeacher, isGuest }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = (): AuthContextType => {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
    return ctx;
};