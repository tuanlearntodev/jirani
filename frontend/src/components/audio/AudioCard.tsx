import { useEffect, useRef } from 'react';
import { Trash2, Loader2, Pencil, Check, X, Music } from 'lucide-react';
import { Audio } from '../../types';
import { getAudioStreamUrl } from '../../api/audio';

interface AudioCardProps {
    audio: Audio;
    isEditing: boolean;
    isDeleting: boolean;
    editTitle: string;
    editDescription: string;
    currentlyPlayingId: Audio['id'] | null;
    onPlay: (id: Audio['id']) => void;
    onEditTitleChange: (v: string) => void;
    onEditDescriptionChange: (v: string) => void;
    onStartEdit: () => void;
    onSaveEdit: () => void;
    onCancelEdit: () => void;
    onDelete: () => void;
}

export const AudioCard = ({
    audio, isEditing, isDeleting, editTitle, editDescription, currentlyPlayingId,
    onPlay, onEditTitleChange, onEditDescriptionChange,
    onStartEdit, onSaveEdit, onCancelEdit, onDelete,
}: AudioCardProps) => {
    const audioRef = useRef<HTMLAudioElement>(null);

    // Pause this track whenever a different one starts playing
    useEffect(() => {
        if (currentlyPlayingId !== audio.id && audioRef.current) {
            audioRef.current.pause();
        }
    }, [currentlyPlayingId, audio.id]);

    return (
        <div className="bg-[#111111] border border-[#2a2a2a] rounded overflow-hidden hover:border-[#7a5e20] transition-all duration-200">
            <div className="bg-[#0A0A0A] px-4 pt-5 pb-3.5 flex flex-col items-center gap-3 border-b border-[#2a2a2a]">
                <div className="w-11 h-11 rounded-xl bg-[#C9A84C] flex items-center justify-center">
                    <Music size={20} className="text-[#0A0A0A]" />
                </div>
                <audio
                    ref={audioRef}
                    controls
                    preload="metadata"
                    onPlay={() => onPlay(audio.id)}
                    className="w-full h-9"
                >
                    <source src={getAudioStreamUrl(audio.id)} />
                </audio>
            </div>

            {isEditing ? (
                <div className="px-3 py-3">
                    <input
                        autoFocus
                        value={editTitle}
                        onChange={(e) => onEditTitleChange(e.target.value)}
                        placeholder="Title..."
                        className="w-full bg-[#0A0A0A] border border-[#7a5e20] rounded-sm px-2 py-1.5 text-[#F0EAD6] text-sm outline-none mb-1.5"
                    />
                    <input
                        value={editDescription}
                        onChange={(e) => onEditDescriptionChange(e.target.value)}
                        placeholder="Description (optional)..."
                        className="w-full bg-[#0A0A0A] border border-[#2a2a2a] rounded-sm px-2 py-1.5 text-[#7a7265] text-xs outline-none focus:border-[#7a5e20] transition-colors mb-2"
                    />
                    <div className="flex gap-2">
                        <button
                            onClick={onSaveEdit}
                            className="flex-1 py-1.5 bg-[#C9A84C] text-[#0A0A0A] font-mono text-[0.6rem] tracking-widest uppercase rounded-sm hover:bg-[#E2C97E] transition-colors flex items-center justify-center gap-1"
                        >
                            <Check size={10} /> Save
                        </button>
                        <button
                            onClick={onCancelEdit}
                            className="flex-1 py-1.5 border border-[#2a2a2a] text-[#7a7265] font-mono text-[0.6rem] tracking-widest uppercase rounded-sm hover:border-[#4a4540] transition-colors flex items-center justify-center gap-1"
                        >
                            <X size={10} /> Cancel
                        </button>
                    </div>
                </div>
            ) : (
                <div className="px-3 py-2.5 flex items-center justify-between gap-2">
                    <div className="flex flex-col min-w-0">
                        <span className="text-sm font-medium text-[#F0EAD6] truncate">{audio.title}</span>
                        {audio.description && (
                            <span className="text-xs text-[#7a7265] truncate">{audio.description}</span>
                        )}
                    </div>
                    <div className="flex gap-1 flex-shrink-0">
                        <button
                            title="Edit"
                            onClick={onStartEdit}
                            className="w-8 h-8 flex items-center justify-center border border-[#2a2a2a] rounded-sm text-[#4a4540] hover:bg-[#1a1a0a] hover:border-[#7a5e20] hover:text-[#C9A84C] transition-colors"
                        >
                            <Pencil size={12} />
                        </button>
                        <button
                            title="Delete"
                            disabled={isDeleting}
                            onClick={onDelete}
                            className="w-8 h-8 flex items-center justify-center border border-[#2a2a2a] rounded-sm text-[#4a4540] hover:bg-[#2a1210] hover:border-[#c0392b] hover:text-[#e07070] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                        >
                            {isDeleting ? <Loader2 size={13} className="animate-spin text-[#e07070]" /> : <Trash2 size={13} />}
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
};