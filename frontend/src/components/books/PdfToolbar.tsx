import { ArrowLeft, ZoomIn, ZoomOut } from 'lucide-react';

const btnClass =
    "flex items-center justify-center w-8 h-8 bg-[#222] border border-[#333] rounded-lg text-[#aaa] cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed transition-colors";

interface PdfToolbarProps {
    scale: number | null;
    onBack: () => void;
    onZoomIn: () => void;
    onZoomOut: () => void;
}

export const PdfToolbar = ({ scale, onBack, onZoomIn, onZoomOut }: PdfToolbarProps) => (
    <div className="flex-shrink-0 flex items-center gap-3 px-4 py-2.5 bg-[#111] border-b border-[#2a2a2a]">
        <button
            onClick={onBack}
            className="flex items-center gap-1.5 text-[#888] bg-transparent border-none cursor-pointer text-xs font-mono"
        >
            <ArrowLeft size={14} /> Back
        </button>
        <div className="ml-auto flex items-center gap-2">
            <button onClick={onZoomOut} disabled={!scale || scale <= 0.5} className={btnClass}>
                <ZoomOut size={15} />
            </button>
            <span className="text-[#888] text-xs font-mono min-w-[36px] text-center">
                {scale ? `${Math.round(scale * 100)}%` : '—'}
            </span>
            <button onClick={onZoomIn} disabled={!scale || scale >= 3} className={btnClass}>
                <ZoomIn size={15} />
            </button>
        </div>
    </div>
);