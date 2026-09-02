import { createContext, useContext, ReactNode } from "react";

export interface AuthData {
    username: string;
    roles: string[];
    [key: string]: unknown;
}

interface AuthContextType {
    auth: AuthData | null;
    login: (data: AuthData) => void;
    logout: () => void;
    isAdmin: boolean;
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

    const login = (data: AuthData) => {
        localStorage.setItem("auth", JSON.stringify(data));
        setAuth(data);
    };

    const logout = () => {
        localStorage.removeItem("auth");
        setAuth(null);
    };

    const isAdmin = auth?.roles?.includes("admin") ?? false;
    const isGuest = !auth;

    return (
        <AuthContext.Provider value={{ auth, login, logout, isAdmin, isGuest }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = (): AuthContextType => {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
    return ctx;
};