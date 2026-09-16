import { useState } from 'react';
import { UserPlus, ShieldCheck, X, Loader2 } from 'lucide-react';
import * as authApi from '../../services/api/auth';

const inputStyle =
    "w-full px-3.5 py-2.5 border border-[#E8E4DE] rounded-[10px] text-[13px] text-[#1C1A17] bg-white outline-none box-border font-sans appearance-none [-webkit-text-fill-color:#1C1A17]";
const labelStyle = "text-xs text-[#6B6560] block mb-1.5 font-sans";

interface AddTeacherModalProps {
    onClose: () => void;
}

export const AddTeacherModal = ({ onClose }: AddTeacherModalProps) => {
    const [step, setStep] = useState<'form' | 'credential'>('form');
    const [firstName, setFirstName] = useState('');
    const [lastName, setLastName] = useState('');
    const [username, setUsername] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [credential, setCredential] = useState('');

    const isValid = firstName.trim() !== '' && lastName.trim() !== '' && username.trim().length >= 3;

    const handleCreate = async () => {
        setLoading(true); setError('');
        try {
            const data = await authApi.createUser({
                username: username.trim(),
                first_name: firstName.trim(),
                last_name: lastName.trim(),
                role: 'teacher',
            });
            setCredential(data.credential);
            setStep('credential');
        } catch (e) {
            setError((e as Error).message || 'Failed to create teacher account.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#1C1A17]/40 backdrop-blur-sm">
            <div className="bg-white rounded-[20px] w-full max-w-[440px] mx-4 shadow-[0_32px_80px_rgba(28,26,23,0.18)] overflow-hidden max-h-[90vh] overflow-y-auto">
                {step === 'credential' ? (
                    <div className="p-8 flex flex-col gap-5 text-center">
                        <div>
                            <div className="w-[52px] h-[52px] rounded-2xl bg-[#F0FAF4] flex items-center justify-center mx-auto mb-3.5">
                                <ShieldCheck size={22} color="#2D7A4F" />
                            </div>
                            <h2 className="text-xl font-bold text-[#1C1A17] mb-2">Teacher Added!</h2>
                            <p className="text-[13px] text-[#6B6560] m-0 leading-relaxed">
                                Give <strong>{username}</strong> their temporary password. They'll be asked to change it on first login.
                            </p>
                        </div>
                        <div className="bg-[#F5EDD8] border-[1.5px] border-[#D4A93A] rounded-2xl px-6 py-5">
                            <p className="text-[11px] text-[#A09890] uppercase tracking-[0.08em] mb-2.5 font-semibold">Temporary Password</p>
                            <div className="font-mono text-[20px] font-bold text-[#B8922A] break-all">{credential}</div>
                        </div>
                        <p className="text-xs text-[#A09890] m-0 text-center leading-relaxed">
                            Write this down somewhere safe — it will not be shown again.
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
                                <span className="text-[19px] font-bold text-[#1C1A17]">Add Teacher</span>
                            </div>
                            <button onClick={onClose} className="w-[34px] h-[34px] rounded-[10px] border border-[#E8E4DE] bg-[#F7F5F2] flex items-center justify-center cursor-pointer text-[#6B6560]">
                                <X size={15} />
                            </button>
                        </div>
                        <div className="p-6 flex flex-col gap-3.5">
                            <div className="px-3.5 py-2.5 bg-[#F5EDD8] rounded-[10px] flex items-center gap-2">
                                <ShieldCheck size={13} color="#B8922A" />
                                <span className="text-[11px] text-[#B8922A] font-medium">Account gets a temporary password and must change it on first login</span>
                            </div>
                            <div className="flex gap-2.5">
                                <div className="flex-1">
                                    <label className={labelStyle}>First name</label>
                                    <input value={firstName} onChange={e => setFirstName(e.target.value)} placeholder="First..." className={inputStyle} />
                                </div>
                                <div className="flex-1">
                                    <label className={labelStyle}>Last name</label>
                                    <input value={lastName} onChange={e => setLastName(e.target.value)} placeholder="Last..." className={inputStyle} />
                                </div>
                            </div>
                            <div>
                                <label className={labelStyle}>Username</label>
                                <input value={username} onChange={e => setUsername(e.target.value)} placeholder="min 3 characters..." className={inputStyle} />
                            </div>
                            {error && <p className="m-0 text-xs text-[#A09890] text-center">{error}</p>}
                            <button onClick={handleCreate} disabled={loading || !isValid}
                                className={`py-3.5 rounded-xl text-sm font-semibold flex items-center justify-center gap-2 ${loading || !isValid ? "bg-[#E8E4DE] text-[#A09890] cursor-not-allowed" : "bg-[#B8922A] text-white cursor-pointer"}`}>
                                {loading ? <><Loader2 size={14} className="animate-spin" /> Creating...</> : <><UserPlus size={14} /> Create Teacher Account</>}
                            </button>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
};