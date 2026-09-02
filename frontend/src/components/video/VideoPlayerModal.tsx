import { useEffect } from 'react';
import { X } from 'lucide-react';
import { Video } from '../../types';
import { getVideoStreamUrl } from '../../services/api/videos';

interface VideoPlayerModalProps {
    video: Video;
    onClose: () => void;
}

export const VideoPlayerModal = ({ video, onClose }: VideoPlayerModalProps) => {
    useEffect(() => {
        const handleKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
        window.addEventListener('keydown', handleKey);
        return () => window.removeEventListener('keydown', handleKey);
    }, [onClose]);

    return (
        <div onClick={onClose} className="fixed inset-0 z-50 bg-black/[0.92] flex flex-col items-center justify-center p-5">
            <div onClick={e => e.stopPropagation()} className="w-full max-w-[960px] flex flex-col gap-3.5">
                <div className="flex items-center justify-between">
                    <p className="text-[15px] font-medium text-[#F0EAD6] m-0">{video.title}</p>
                    <button onClick={onClose} className="w-[34px] h-[34px] rounded-[10px] border border-white/15 bg-white/[0.08] flex items-center justify-center cursor-pointer text-[#F0EAD6]">
                        <X size={15} />
                    </button>
                </div>
                <video autoPlay controls className="w-full rounded-xl bg-black max-h-[75vh]">
                    <source src={getVideoStreamUrl(video.id)} />
                </video>
                {video.description && <p className="text-[13px] text-[#A09890] m-0">{video.description}</p>}
                {video.tags && video.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                        {video.tags.map(tag => (
                            <span key={tag.id || tag.name} className="text-[11px] px-2.5 py-0.5 rounded-full bg-white/10 text-[#A09890]">
                                {tag.name}
                            </span>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};