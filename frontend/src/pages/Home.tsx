// src/pages/Home.tsx
import { useState, FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { BookOpen } from "lucide-react";
import * as authApi from "../services/api/auth";
import { LoginForm } from "../components/auth/LoginForm";

const Home = () => {
    const { login: loginToContext } = useAuth();
    const navigate = useNavigate();

    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [showPassword, setShowPassword] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    const handleLogin = async (e: FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        if (!username.trim() || !password.trim()) { setError("Please enter username and password."); return; }
        setLoading(true); setError("");
        try {
            const data = await authApi.login(username.trim(), password);
            loginToContext(data);
            navigate("/library");
        } catch (e) {
            setError((e as Error).message || "Login failed.");
        } finally { setLoading(false); }
    };

    return (
        <div className="min-h-screen bg-[#FAFAF9] flex items-center justify-center font-sans p-6">
            <div className="w-full max-w-[420px]">

                <div className="text-center mb-10">
                    <div className="w-16 h-16 rounded-[18px] bg-[#F5EDD8] flex items-center justify-center mx-auto mb-4 shadow-[0_4px_16px_rgba(184,146,42,0.18)]">
                        <BookOpen size={28} color="#B8922A" />
                    </div>
                    <h1 className="text-[30px] font-bold text-[#1C1A17] mb-1.5 tracking-[-0.02em]">Offlib LLC</h1>
                </div>

                <div className="bg-white rounded-[20px] border border-[#E8E4DE] shadow-[0_4px_24px_rgba(28,26,23,0.07)] overflow-hidden">
                    <div className="px-7 pt-7 pb-5">
                        <p className="text-[10px] text-[#A09890] uppercase tracking-[0.1em] mb-5 font-semibold">Sign In</p>

                        <LoginForm
                            username={username}
                            password={password}
                            showPassword={showPassword}
                            loading={loading}
                            error={error}
                            onUsernameChange={setUsername}
                            onPasswordChange={setPassword}
                            onToggleShowPassword={() => setShowPassword(p => !p)}
                            onSubmit={handleLogin}
                            onForgotPassword={() => { /* TODO: no backend route yet */ }}
                        />
                    </div>

                    <div className="flex items-center gap-3 px-7">
                        <div className="flex-1 h-px bg-[#E8E4DE]" />
                        <span className="text-xs text-[#A09890]">or</span>
                        <div className="flex-1 h-px bg-[#E8E4DE]" />
                    </div>

                    <div className="px-7 pt-5 pb-7 flex flex-col gap-2.5">
                        <button onClick={() => navigate("/library")}
                            className="w-full py-3.5 bg-[#F7F5F2] hover:bg-[#F0EDE8] text-[#6B6560] border border-[#E8E4DE] rounded-xl text-sm font-medium cursor-pointer transition-colors">
                            Continue as Student
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Home;