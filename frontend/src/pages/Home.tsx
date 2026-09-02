import { useState, FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { BookOpen } from "lucide-react";
import { SignupData } from "../types";
import * as authApi from "../services/api/auth";
import { useAdminExists } from "../hooks/useAdminExists";
import { LoginForm } from "../components/auth/LoginForm";
import { ForgotPasswordForm } from "../components/auth/ForgotPasswordForm";
import { SignupModal } from "../components/auth/SignupModal";

type ForgotMode = "idle" | "enter";

const Home = () => {
    const { login: loginToContext } = useAuth();
    const navigate = useNavigate();
    const { adminExists, setAdminExists } = useAdminExists();

    // Login state
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [showPassword, setShowPassword] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    // Forgot-password state
    const [forgotMode, setForgotMode] = useState<ForgotMode>("idle");
    const [forgotUsername, setForgotUsername] = useState("");
    const [otp, setOtp] = useState("");
    const [newPassword, setNewPassword] = useState("");
    const [showNewPassword, setShowNewPassword] = useState(false);
    const [forgotLoading, setForgotLoading] = useState(false);
    const [forgotError, setForgotError] = useState("");

    // Signup state
    const [showSignup, setShowSignup] = useState(false);
    const [showSignupPassword, setShowSignupPassword] = useState(false);
    const [signupLoading, setSignupLoading] = useState(false);
    const [signupError, setSignupError] = useState("");
    const [signupData, setSignupData] = useState<SignupData>({
        username: "", password: "", first_name: "", last_name: ""
    });
    const [recoveryCode, setRecoveryCode] = useState("");
    const [showRecoveryCode, setShowRecoveryCode] = useState(false);

    const resetForgotState = () => {
        setForgotMode("idle");
        setForgotUsername("");
        setOtp("");
        setNewPassword("");
        setForgotError("");
        setShowNewPassword(false);
    };

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

    const verifyCode = async () => {
        setForgotLoading(true); setForgotError("");
        try {
            await authApi.verifyResetCode(forgotUsername.trim(), otp, newPassword);
            resetForgotState();
            setError("Password reset! Please log in.");
        } catch (e) {
            setForgotError((e as Error).message || "Failed to verify.");
        } finally { setForgotLoading(false); }
    };

    const handleSignup = async () => {
        setSignupLoading(true); setSignupError("");
        try {
            const data = await authApi.signup(signupData);
            await authApi.makeAdmin(signupData.username);
            setRecoveryCode(data.recovery_code);
            setShowRecoveryCode(true);
            setAdminExists(true);
        } catch (e) {
            setSignupError((e as Error).message || "Signup failed.");
        } finally { setSignupLoading(false); }
    };

    const closeSignupModal = () => {
        setShowSignup(false);
        setShowRecoveryCode(false);
        setRecoveryCode("");
        setSignupData({ username: "", password: "", first_name: "", last_name: "" });
        setError("Account created! You can now log in.");
    };

    const signupValid =
        signupData.first_name.trim() !== "" &&
        signupData.last_name.trim() !== "" &&
        signupData.username.trim().length >= 4 &&
        signupData.password.length >= 15;

    const forgotValid = forgotUsername.trim() !== "" && otp.trim() !== "" && newPassword.length >= 15;

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
                        <p className="text-[10px] text-[#A09890] uppercase tracking-[0.1em] mb-5 font-semibold">Admin Login</p>

                        {forgotMode === "idle" ? (
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
                                onForgotPassword={() => { setForgotMode("enter"); setForgotError(""); setError(""); }}
                            />
                        ) : (
                            <ForgotPasswordForm
                                username={forgotUsername}
                                otp={otp}
                                newPassword={newPassword}
                                showNewPassword={showNewPassword}
                                loading={forgotLoading}
                                error={forgotError}
                                valid={forgotValid}
                                onUsernameChange={setForgotUsername}
                                onOtpChange={setOtp}
                                onNewPasswordChange={setNewPassword}
                                onToggleShowNewPassword={() => setShowNewPassword(p => !p)}
                                onSubmit={verifyCode}
                                onCancel={resetForgotState}
                            />
                        )}
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

                        {adminExists === false && (
                            <button onClick={() => setShowSignup(true)}
                                className="w-full py-3.5 bg-white hover:bg-[#F5EDD8] text-[#B8922A] border-[1.5px] border-[#B8922A] rounded-xl text-sm font-medium cursor-pointer transition-colors">
                                Create Admin Account
                            </button>
                        )}
                    </div>
                </div>
            </div>

            {showSignup && (
                <SignupModal
                    signupData={signupData}
                    showPassword={showSignupPassword}
                    loading={signupLoading}
                    error={signupError}
                    valid={Boolean(signupValid)}
                    showRecoveryCode={showRecoveryCode}
                    recoveryCode={recoveryCode}
                    onFieldChange={(field, value) => setSignupData(p => ({ ...p, [field]: value }))}
                    onToggleShowPassword={() => setShowSignupPassword(p => !p)}
                    onSubmit={handleSignup}
                    onClose={() => setShowSignup(false)}
                    onAcknowledgeRecoveryCode={closeSignupModal}
                />
            )}
        </div>
    );
};

export default Home;