import { useState } from 'react';
import { UserPlus, ShieldCheck, X, Eye, EyeOff, Loader2 } from 'lucide-react';
import { SignupData } from '../../types';
import * as authApi from '../../services/api/auth';

const inputStyle =
    "w-full px-3.5 py-2.5 border border-[#E8E4DE] rounded-[10px] text-[13px] text-[#1C1A17] bg-white outline-none box-border font-sans appearance-none [-webkit-text-fill-color:#1C1A17]";
const labelStyle = "text-xs text-[#6B6560] block mb-1.5 font-sans";

interface AddAdminModalProps {
    onClose: () => void;
}

export const AddAdminModal = ({ onClose }: AddAdminModalProps) => {
    const [step, setStep] = useState<'form' | 'recovery'>('form');
    const [formData, setFormData] = useState<SignupData>({ username: '', password: '', first_name: '', last_name: '' });
    const [showPassword, setShowPassword] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [recoveryCode, setRecoveryCode] = useState('');

    const isValid =
        formData.first_name.trim() !== '' &&
        formData.last_name.trim() !== '' &&
        formData.username.trim().length >= 4 &&
        formData.password.length >= 15;

    const handleCreate = async () => {
        setLoading(true); setError('');
        try {
            const data = await authApi.signup(formData);
            await authApi.makeAdmin(formData.username);
            setRecoveryCode(data.recovery_code || 'N/A');
            setStep('recovery');
        } catch (e) {
            setError((e as Error).message || 'Failed to create admin.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#1C1A17]/40 backdrop-blur-sm">
            <div className="bg-white rounded-[20px] w-full max-w-[440px] mx-4 shadow-[0_32px_80px_rgba(28,26,23,0.18)] overflow-hidden max-h-[90vh] overflow-y-auto">
                {step === 'recovery' ? (
                    <div className="p-8 flex flex-col gap-5 text-center">
                        <div>
                            <div className="w-[52px] h-[52px] rounded-2xl bg-[#F0FAF4] flex items-center justify-center mx-auto mb-3.5">
                                <ShieldCheck size={22} color="#2D7A4F" />
                            </div>
                            <h2 className="text-xl font-bold text-[#1C1A17] mb-2">Admin Created!</h2>
                            <p className="text-[13px] text-[#6B6560] m-0 leading-relaxed">Give <strong>{formData.username}</strong> their recovery code.</p>
                        </div>
                        <div className="bg-[#F5EDD8] border-[1.5px] border-[#D4A93A] rounded-2xl px-6 py-5">
                            <p className="text-[11px] text-[#A09890] uppercase tracking-[0.08em] mb-2.5 font-semibold">Recovery Code</p>
                            <div className="font-mono text-[28px] font-bold text-[#B8922A] tracking-[0.25em]">{recoveryCode}</div>
                        </div>
                        <p className="text-xs text-[#A09890] m-0 text-center leading-relaxed">
                            Write this down somewhere safe — this code will not be shown again.
                        </p>
                        <button onClick={onClose} className="py-3.5 bg-[#B8922A] text-white border-none rounded-xl text-sm font-semibold cursor-pointer">Done</button>
                    </div>
                ) : (
                    <>
                        <div className="px-6 pt-5.5 flex items-center justify-between">
                            <div className="flex items-center gap-2.5">
                                <div className="w-8 h-8 rounded-[9px] bg-[#F5EDD8] flex items-center justify-center">
                                    <UserPlus size={14} color="#B8922A" />
                                </div>
                                <span className="text-[19px] font-bold text-[#1C1A17]">Add Admin</span>
                            </div>
                            <button onClick={onClose} className="w-[34px] h-[34px] rounded-[10px] border border-[#E8E4DE] bg-[#F7F5F2] flex items-center justify-center cursor-pointer text-[#6B6560]">
                                <X size={15} />
                            </button>
                        </div>
                        <div className="p-6 flex flex-col gap-3.5">
                            <div className="px-3.5 py-2.5 bg-[#F5EDD8] rounded-[10px] flex items-center gap-2">
                                <ShieldCheck size={13} color="#B8922A" />
                                <span className="text-[11px] text-[#B8922A] font-medium">This account will have full admin access</span>
                            </div>
                            <div className="flex gap-2.5">
                                <div className="flex-1">
                                    <label className={labelStyle}>First name</label>
                                    <input value={formData.first_name} onChange={e => setFormData(p => ({ ...p, first_name: e.target.value }))} placeholder="First..." className={inputStyle} />
                                </div>
                                <div className="flex-1">
                                    <label className={labelStyle}>Last name</label>
                                    <input value={formData.last_name} onChange={e => setFormData(p => ({ ...p, last_name: e.target.value }))} placeholder="Last..." className={inputStyle} />
                                </div>
                            </div>
                            <div>
                                <label className={labelStyle}>Username</label>
                                <input value={formData.username} onChange={e => setFormData(p => ({ ...p, username: e.target.value }))} placeholder="min 4 characters..." className={inputStyle} />
                            </div>
                            <div>
                                <label className={labelStyle}>Password</label>
                                <div className="relative">
                                    <input
                                        type={showPassword ? "text" : "password"}
                                        value={formData.password}
                                        onChange={e => setFormData(p => ({ ...p, password: e.target.value }))}
                                        placeholder="min 15 characters..."
                                        className={`${inputStyle} pr-10`}
                                    />
                                    <button type="button" onClick={() => setShowPassword(p => !p)}
                                        className="absolute right-3 top-1/2 -translate-y-1/2 bg-transparent border-none cursor-pointer text-[#A09890] p-0 flex">
                                        {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                                    </button>
                                </div>
                                {formData.password.length > 0 && formData.password.length < 15 && (
                                    <p className="text-[11px] text-[#D94F3D] mt-1 mb-0">{15 - formData.password.length} more characters needed</p>
                                )}
                            </div>
                            {error && <p className="m-0 text-xs text-[#A09890] text-center">{error}</p>}
                            <button onClick={handleCreate} disabled={loading || !isValid}
                                className={`py-3.5 rounded-xl text-sm font-semibold flex items-center justify-center gap-2 ${loading || !isValid ? "bg-[#E8E4DE] text-[#A09890] cursor-not-allowed" : "bg-[#B8922A] text-white cursor-pointer"}`}>
                                {loading ? <><Loader2 size={14} className="animate-spin" /> Creating...</> : <><UserPlus size={14} /> Create Admin Account</>}
                            </button>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
};