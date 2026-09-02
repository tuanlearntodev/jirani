import { BookOpen, Loader2, Eye, EyeOff, X } from 'lucide-react';
import { SignupData } from '../../types';

const inputBase =
    "w-full px-3.5 py-2.5 border border-[#E8E4DE] rounded-[10px] text-sm text-[#1C1A17] bg-white outline-none box-border font-sans appearance-none [-webkit-text-fill-color:#1C1A17]";
const labelStyle = "text-xs text-[#6B6560] block mb-1.5 font-sans";

interface SignupModalProps {
    signupData: SignupData;
    showPassword: boolean;
    loading: boolean;
    error: string;
    valid: boolean;
    showRecoveryCode: boolean;
    recoveryCode: string;
    onFieldChange: (field: keyof SignupData, value: string) => void;
    onToggleShowPassword: () => void;
    onSubmit: () => void;
    onClose: () => void;
    onAcknowledgeRecoveryCode: () => void;
}

export const SignupModal = ({
    signupData, showPassword, loading, error, valid,
    showRecoveryCode, recoveryCode,
    onFieldChange, onToggleShowPassword, onSubmit, onClose, onAcknowledgeRecoveryCode,
}: SignupModalProps) => (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#1C1A17]/40 backdrop-blur-sm">
        <div className="bg-white rounded-[20px] w-full max-w-[440px] mx-4 shadow-[0_32px_80px_rgba(28,26,23,0.18)] overflow-hidden max-h-[90vh] overflow-y-auto">

            {showRecoveryCode ? (
                <div className="p-8 flex flex-col gap-5 text-center">
                    <div>
                        <div className="w-[52px] h-[52px] rounded-2xl bg-[#F5EDD8] flex items-center justify-center mx-auto mb-3.5">
                            <BookOpen size={22} color="#B8922A" />
                        </div>
                        <h2 className="text-xl font-bold text-[#1C1A17] mb-2">Account Created!</h2>
                        <p className="text-[13px] text-[#6B6560] m-0 leading-relaxed">
                            Write down your recovery code. You'll need it to reset your password if you ever forget it.
                        </p>
                    </div>
                    <div className="bg-[#F5EDD8] border-[1.5px] border-[#D4A93A] rounded-2xl px-6 py-5">
                        <p className="text-[11px] text-[#A09890] uppercase tracking-[0.08em] mb-2.5 font-semibold">Recovery Code</p>
                        <div className="font-mono text-[28px] font-bold text-[#B8922A] tracking-[0.25em]">
                            {recoveryCode}
                        </div>
                    </div>
                    <p className="text-xs text-[#A09890] m-0 text-center leading-relaxed">
                        Write this down somewhere safe — this code will not be shown again.
                    </p>
                    <button
                        onClick={onAcknowledgeRecoveryCode}
                        className="py-3.5 bg-[#B8922A] text-white border-none rounded-xl text-sm font-semibold cursor-pointer">
                        I've written it down — Continue
                    </button>
                </div>
            ) : (
                <>
                    <div className="px-6 pt-5.5 flex items-center justify-between">
                        <span className="text-[19px] font-bold text-[#1C1A17]">Create Admin Account</span>
                        <button onClick={onClose} className="w-[34px] h-[34px] rounded-[10px] border border-[#E8E4DE] bg-[#F7F5F2] flex items-center justify-center cursor-pointer text-[#6B6560]">
                            <X size={15} />
                        </button>
                    </div>
                    <div className="p-6 flex flex-col gap-3.5">
                        <div className="flex gap-2.5">
                            <div className="flex-1">
                                <label className={labelStyle}>First name</label>
                                <input value={signupData.first_name} onChange={e => onFieldChange('first_name', e.target.value)} placeholder="First..." className={inputBase} />
                            </div>
                            <div className="flex-1">
                                <label className={labelStyle}>Last name</label>
                                <input value={signupData.last_name} onChange={e => onFieldChange('last_name', e.target.value)} placeholder="Last..." className={inputBase} />
                            </div>
                        </div>
                        <div>
                            <label className={labelStyle}>Username</label>
                            <input value={signupData.username} onChange={e => onFieldChange('username', e.target.value)} placeholder="min 4 characters..." className={inputBase} />
                        </div>
                        <div>
                            <label className={labelStyle}>Password</label>
                            <div className="relative">
                                <input
                                    type={showPassword ? "text" : "password"}
                                    value={signupData.password}
                                    onChange={e => onFieldChange('password', e.target.value)}
                                    placeholder="min 15 characters..."
                                    className={`${inputBase} pr-10`}
                                />
                                <button type="button" onClick={onToggleShowPassword}
                                    className="absolute right-3 top-1/2 -translate-y-1/2 bg-transparent border-none cursor-pointer text-[#A09890] p-0 flex">
                                    {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                                </button>
                            </div>
                            {signupData.password.length > 0 && signupData.password.length < 15 && (
                                <p className="text-[11px] text-[#D94F3D] mt-1 mb-0">
                                    {15 - signupData.password.length} more characters needed
                                </p>
                            )}
                        </div>
                        {error && (
                            <p className="m-0 text-xs text-[#A09890] text-center">
                                {error}
                            </p>
                        )}
                        <button onClick={onSubmit} disabled={loading || !valid}
                            className={`py-3.5 rounded-xl text-sm font-semibold flex items-center justify-center gap-2 ${loading || !valid ? "bg-[#E8E4DE] text-[#A09890] cursor-not-allowed" : "bg-[#B8922A] text-white cursor-pointer"}`}>
                            {loading ? <><Loader2 size={14} className="animate-spin" /> Creating...</> : "Create Account"}
                        </button>
                    </div>
                </>
            )}
        </div>
    </div>
);