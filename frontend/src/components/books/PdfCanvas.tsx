import { RefObject, TouchEvent, useRef } from 'react';
import { Loader2 } from 'lucide-react';

interface PdfCanvasProps {
    containerRef: RefObject<HTMLDivElement | null>;
    canvasRef: RefObject<HTMLCanvasElement | null>;
    loading: boolean;
    error: string | null;
    rendering: boolean;
    onSwipeNext: () => void;
    onSwipePrev: () => void;
}

export const PdfCanvas = ({
    containerRef, canvasRef, loading, error, rendering, onSwipeNext, onSwipePrev,
}: PdfCanvasProps) => {
    const touchStartX = useRef<number | null>(null);
    const touchStartY = useRef<number | null>(null);

    const handleTouchStart = (e: TouchEvent<HTMLDivElement>) => {
        touchStartX.current = e.touches[0].clientX;
        touchStartY.current = e.touches[0].clientY;
    };

    const handleTouchEnd = (e: TouchEvent<HTMLDivElement>) => {
        if (touchStartX.current === null || touchStartY.current === null) return;
        const dx = e.changedTouches[0].clientX - touchStartX.current;
        const dy = e.changedTouches[0].clientY - touchStartY.current;
        if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 40) {
            if (dx < 0) onSwipeNext();
            else onSwipePrev();
        }
        touchStartX.current = null;
        touchStartY.current = null;
    };

    return (
        <div
            ref={containerRef}
            onTouchStart={handleTouchStart}
            onTouchEnd={handleTouchEnd}
            className="flex-1 overflow-auto flex items-start justify-center px-2 py-4"
        >
            {loading && (
                <div className="flex items-center gap-2.5 text-[#666] mt-20">
                    <Loader2 size={20} className="animate-spin" />
                    <span className="font-mono text-sm">Loading book…</span>
                </div>
            )}
            {error && (
                <div className="text-[#e06c75] font-mono text-sm mt-20">{error}</div>
            )}
            {!loading && !error && (
                <div className="relative">
                    {rendering && (
                        <div className="absolute inset-0 flex items-center justify-center bg-[#1a1a1a]/50 z-10">
                            <Loader2 size={22} className="text-[#888] animate-spin" />
                        </div>
                    )}
                    <canvas ref={canvasRef} className="block shadow-[0_4px_32px_rgba(0,0,0,0.6)] rounded-sm" />
                </div>
            )}
        </div>
    );
};