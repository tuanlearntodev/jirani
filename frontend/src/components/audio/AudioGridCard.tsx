import { useState, useEffect, useRef } from 'react';
import { Trash2, Loader2, Pencil, Check, X, Music } from 'lucide-react';
import { Audio } from '../../types';
import { getAudioStreamUrl } from '../../services/api/audio';
import * as audioApi from '../../services/api/audio';

const inputStyle =
    "w-full px-3.5 py-2.5 border border-[#E8E4DE] rounded-[10px] text-[13px] text-[#1C1A17] bg-white outline-none box-border font-sans appearance-none [-webkit-text-fill-color:#1C1A17]";

interface AudioGridCardProps {
    audio: Audio;
    isAdmin: boolean;
    onDelete: (id: Audio['id']) => void;
    onUpdate: (updated: Audio) => void;
    onPlay: (id: Audio['id']) => void;
    currentlyPlaying: Audio['id'] | null;
}

export const AudioGridCard = ({ audio, isAdmin, onDelete, onUpdate, onPlay, currentlyPlaying }: AudioGridCardProps) => {
    const [deleting, setDeleting] = useState(false);
    const [editing, setEditing] = useState(false);
    const [editTitle, setEditTitle] = useState(audio.title);
    const [editDesc, setEditDesc] = useState(audio.description || '');
    const [editTags, setEditTags] = useState(audio.tags?.map(t => t.name).join(', ') || '');
    const audioRef = useRef<HTMLAudioElement>(null);

    useEffect(() => {
        if (currentlyPlaying !== audio.id && audioRef.current) audioRef.current.pause();
    }, [currentlyPlaying, audio.id]);

    const handleDelete = async () => {
        setDeleting(true);
        try {
            await audioApi.deleteAudio(audio.id);
            onDelete(audio.id);
        } finally {
            setDeleting(false);
        }
    };

    const saveEdit = async () => {
        try {
            const updated = await audioApi.updateAudio(audio.id, editTitle, editDesc, editTags);
            onUpdate(updated);
            setEditing(false);
        } catch {
            // leave the edit form open so the admin can retry
        }
    };

    const editInputStyle = `${inputStyle} px-3 py-2 rounded-[9px]`;

    return (
        <div className="bg-white rounded-2xl overflow-hidden border border-[#E8E4DE] shadow-[0_1px_4px_rgba(28,26,23,0.05)]">
            <div className="bg-gradient-to-br from-[#F5EDD8] to-[#EDE0C4] pt-5 px-4 pb-3.5 flex flex-col items-center gap-3">
                <div className="w-12 h-12 rounded-2xl bg-[#B8922A] flex items-center justify-center shadow-[0_4px_12px_rgba(184,146,42,0.3)]">
                    <Music size={22} color="#fff" />
                </div>
                <audio ref={audioRef} controls onPlay={() => onPlay(audio.id)} className="w-full h-9">
                    <source src={getAudioStreamUrl(audio.id)} />
                </audio>
            </div>

            {editing ? (
                <div className="p-3.5 flex flex-col gap-2 border-t border-[#E8E4DE]">
                    <input autoFocus value={editTitle} onChange={e => setEditTitle(e.target.value)} placeholder="Title..." className={`${editInputStyle} border-[1.5px] border-[#B8922A]`} />
                    <input value={editDesc} onChange={e => setEditDesc(e.target.value)} placeholder="Description (optional)..." className={`${editInputStyle} text-xs text-[#6B6560]`} />
                    <input value={editTags} onChange={e => setEditTags(e.target.value)} placeholder="Tags (comma separated)..." className={`${editInputStyle} text-xs text-[#6B6560]`} />
                    <div className="flex gap-2">
                        <button onClick={saveEdit} className="flex-1 py-2 bg-[#B8922A] text-white border-none rounded-[9px] text-xs font-semibold cursor-pointer flex items-center justify-center gap-1.5">
                            <Check size={12} /> Save
                        </button>
                        <button onClick={() => setEditing(false)} className="flex-1 py-2 bg-[#F7F5F2] text-[#6B6560] border border-[#E8E4DE] rounded-[9px] text-xs cursor-pointer flex items-center justify-center gap-1.5">
                            <X size={12} /> Cancel
                        </button>
                    </div>
                </div>
            ) : (
                <div className="px-3.5 py-3 flex items-start justify-between gap-2.5 border-t border-[#E8E4DE]">
                    <div className="min-w-0 flex-1">
                        <p className="text-[13px] font-medium text-[#1C1A17] overflow-hidden text-ellipsis whitespace-nowrap mb-1">{audio.title}</p>
                        {audio.tags && audio.tags.length > 0 && (
                            <div className="flex flex-wrap gap-1">
                                {audio.tags.slice(0, 3).map(tag => (
                                    <span key={tag.id || tag.name} className="text-[10px] px-2 py-0.5 rounded-full bg-[#F5EDD8] text-[#B8922A] font-semibold">
                                        {tag.name}
                                    </span>
                                ))}
                                {audio.tags.length > 3 && <span className="text-[10px] text-[#A09890]">+{audio.tags.length - 3}</span>}
                            </div>
                        )}
                    </div>
                    {isAdmin && (
                        <div className="flex gap-1.5 flex-shrink-0">
                            <button onClick={() => setEditing(true)} className="w-[30px] h-[30px] rounded-lg border border-[#E8E4DE] bg-white cursor-pointer flex items-center justify-center text-[#6B6560]">
                                <Pencil size={12} />
                            </button>
                            <button onClick={handleDelete} disabled={deleting} className="w-[30px] h-[30px] rounded-lg border border-[#FADADD] bg-[#FEF2F0] cursor-pointer flex items-center justify-center text-[#D94F3D] disabled:opacity-40">
                                {deleting ? <Loader2 size={12} className="animate-spin" /> : <Trash2 size={12} />}
                            </button>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};