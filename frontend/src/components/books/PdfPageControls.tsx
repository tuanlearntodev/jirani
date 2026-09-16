import { ChevronLeft, ChevronRight } from 'lucide-react';

const btnClass =
    "flex items-center justify-center w-8 h-8 bg-[#222] border border-[#333] rounded-lg text-[#aaa] cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed transition-colors";

interface PdfPageControlsProps {
    currentPage: number;
    totalPages: number;
    rendering: boolean;
    onPrev: () => void;
    onNext: () => void;
}

export const PdfPageControls = ({ currentPage, totalPages, rendering, onPrev, onNext }: PdfPageControlsProps) => {
    if (totalPages === 0) return null;

    return (
        <div className="flex-shrink-0 flex items-center justify-center gap-4 py-3 bg-[#111] border-t border-[#2a2a2a]">
            <button
                onClick={onPrev}
                disabled={currentPage <= 1 || rendering}
                className={`${btnClass} w-11 h-11 rounded-[10px]`}
            >
                <ChevronLeft size={18} />
            </button>
            <span className="text-[#666] font-mono text-sm">
                {currentPage} / {totalPages}
            </span>
            <button
                onClick={onNext}
                disabled={currentPage >= totalPages || rendering}
                className={`${btnClass} w-11 h-11 rounded-[10px]`}
            >
                <ChevronRight size={18} />
            </button>
        </div>
    );
};