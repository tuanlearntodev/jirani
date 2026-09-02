import { Eye, EyeOff } from 'lucide-react';

const inputBase =
    "w-full px-3.5 py-2.5 border border-[#E8E4DE] rounded-[10px] text-sm text-[#1C1A17] bg-white outline-none box-border font-sans appearance-none [-webkit-text-fill-color:#1C1A17]";

interface ForgotPasswordFormProps {
    username: string;
    otp: string;
    newPassword: string;
    showNewPassword: boolean;
    loading: boolean;
    error: string;
    valid: boolean;
    onUsernameChange: (v: string) => void;
    onOtpChange: (v: string) => void;
    onNewPasswordChange: (v: string) => void;
    onToggleShowNewPassword: () => void;
    onSubmit: () => void;
    onCancel: () => void;
}

export const ForgotPasswordForm = ({
    username, otp, newPassword, showNewPassword, loading, error, valid,
    onUsernameChange, onOtpChange, onNewPasswordChange, onToggleShowNewPassword,
    onSubmit, onCancel,
}: ForgotPasswordFormProps) => (
    <div className="flex flex-col gap-2 border-t border-[#F0EDE8] pt-4 mt-1">
        <p className="text-xs text-[#6B6560] m-0">
            Enter your username and the recovery code you saved when you created your account.
        </p>
        <input value={username} onChange={e => onUsernameChange(e.target.value)} placeholder="Your username..." className={inputBase} />
        <input value={otp} onChange={e => onOtpChange(e.target.value)} placeholder="6-digit recovery code..." className={inputBase} />
        <div className="relative">
            <input
                type={showNewPassword ? "text" : "password"}
                value={newPassword}
                onChange={e => onNewPasswordChange(e.target.value)}
                placeholder="New password (min 15 chars)..."
                className={`${inputBase} pr-10`}
            />
            <button type="button" onClick={onToggleShowNewPassword}
                className="absolute right-3 top-1/2 -translate-y-1/2 bg-transparent border-none cursor-pointer text-[#A09890] p-0 flex">
                {showNewPassword ? <EyeOff size={15} /> : <Eye size={15} />}
            </button>
        </div>
        {newPassword.length > 0 && newPassword.length < 15 && (
            <p className="text-[11px] text-[#D94F3D] m-0">
                {15 - newPassword.length} more characters needed
            </p>
        )}
        {error && (
            <p className="m-0 text-xs text-[#A09890] text-center">
                {error}
            </p>
        )}
        <button type="button" onClick={onSubmit} disabled={loading || !valid}
            className={`py-2.5 rounded-[10px] text-[13px] font-semibold ${loading || !valid ? "bg-[#E8E4DE] text-[#A09890] cursor-not-allowed" : "bg-[#B8922A] text-white cursor-pointer"}`}>
            {loading ? "Verifying..." : "Reset Password"}
        </button>
        <button type="button" onClick={onCancel}
            className="bg-transparent border-none text-[#A09890] text-xs cursor-pointer">
            Cancel
        </button>
    </div>
);