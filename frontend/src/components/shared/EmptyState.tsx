import { LucideIcon, Plus } from 'lucide-react';

interface EmptyStateProps {
    icon: LucideIcon;
    label: string; // e.g. "books", "audio", "videos"
    onUpload: () => void;
    isAdmin: boolean;
}

export const EmptyState = ({ icon: Icon, label, onUpload, isAdmin }: EmptyStateProps) => (
    <div className="flex flex-col items-center justify-center h-full gap-4 text-center">
        <div className="w-[68px] h-[68px] rounded-[20px] bg-[#F5EDD8] flex items-center justify-center">
            <Icon size={28} color="#B8922A" />
        </div>
        <div>
            <p className="text-xl font-bold text-[#1C1A17] mb-1.5">No {label} yet</p>
            <p className="text-[13px] text-[#A09890] m-0">
                {isAdmin ? `Upload some ${label} to get started` : "Nothing here yet — check back later"}
            </p>
        </div>
        {isAdmin && (
            <button onClick={onUpload} className="px-[22px] py-2.5 bg-[#B8922A] text-white border-none rounded-[10px] text-[13px] font-semibold cursor-pointer flex items-center gap-2">
                <Plus size={14} /> Add {label}
            </button>
        )}
    </div>
);