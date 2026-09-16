import { useState, MouseEvent } from 'react';
import { Trash2, Loader2, Pencil, Check, X } from 'lucide-react';
import { Video } from '../../types';
import { getVideoStreamUrl } from '../../services/api/videos';
import * as videosApi from '../../services/api/videos';

const inputStyle =
    "w-full px-3.5 py-2.5 border border-[#E8E4DE] rounded-[10px] text-[13px] text-[#1C1A17] bg-white outline-none box-border font-sans appearance-none [-webkit-text-fill-color:#1C1A17]";

interface VideoGridCardProps {
    video: Video;
    isAdmin: boolean;
    onDelete: (id: Video['id']) => void;
    onUpdate: (updated: Video) => void;
    onPlay: (video: Video) => void;
}

export const VideoGridCard = ({ video, isAdmin, onDelete, onUpdate, onPlay }: VideoGridCardProps) => {
    const [deleting, setDeleting] = useState(false);
    const [editing, setEditing] = useState(false);
    const [editTitle, setEditTitle] = useState(video.title);
    const [editDesc, setEditDesc] = useState(video.description || '');
    const [editTags, setEditTags] = useState(video.tags?.map(t => t.name).join(', ') || '');

    const handleDelete = async (e: MouseEvent) => {
        e.stopPropagation();
        setDeleting(true);
        try {
            await videosApi.deleteVideo(video.id);
            onDelete(video.id);
        } finally {
            setDeleting(false);
        }
    };

    const saveEdit = async () => {
        try {
            const updated = await videosApi.updateVideo(video.id, editTitle, editDesc, editTags);
            onUpdate(updated);
            setEditing(false);
        } catch {
            // leave the edit form open so the admin can retry
        }
    };

    const editInputStyle = `${inputStyle} px-3 py-2 rounded-[9px]`;

    return (
        <div className="group bg-white rounded-2xl overflow-hidden border border-[#E8E4DE] shadow-[0_1px_4px_rgba(28,26,23,0.05)] hover:shadow-[0_8px_28px_rgba(28,26,23,0.10)] transition-all">
            <div onClick={() => !editing && onPlay(video)} className="relative aspect-video bg-black cursor-pointer overflow-hidden">
                <video preload="metadata" muted className="w-full h-full object-cover block group-hover:scale-[1.03] transition-transform duration-300">
                    <source src={`${getVideoStreamUrl(video.id)}#t=1`} />
                </video>
                <div className="absolute inset-0 flex items-center justify-center bg-black/15 group-hover:bg-black/30 transition-colors">
                    <div className="w-11 h-11 rounded-full bg-white/75 group-hover:bg-white/95 flex items-center justify-center transition-all group-hover:scale-110">
                        <div className="w-0 h-0 border-t-[9px] border-t-transparent border-b-[9px] border-b-transparent border-l-[15px] border-l-[#1C1A17] ml-1" />
                    </div>
                </div>
                {isAdmin && (
                    <div className="absolute top-2 right-2 flex gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button onClick={e => { e.stopPropagation(); setEditing(true); }}
                            className="w-[30px] h-[30px] rounded-lg border-none bg-white/90 cursor-pointer flex items-center justify-center text-[#6B6560]">
                            <Pencil size={12} />
                        </button>
                        <button onClick={handleDelete} disabled={deleting}
                            className="w-[30px] h-[30px] rounded-lg border-none bg-white/90 cursor-pointer flex items-center justify-center text-[#D94F3D] disabled:opacity-40">
                            {deleting ? <Loader2 size={12} className="animate-spin" /> : <Trash2 size={12} />}
                        </button>
                    </div>
                )}
            </div>

            {editing ? (
                <div className="p-3.5 flex flex-col gap-2">
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
                <div className="px-3.5 pt-2.5 pb-3">
                    <p className="text-[13px] font-medium text-[#1C1A17] overflow-hidden text-ellipsis whitespace-nowrap mb-1">{video.title}</p>
                    {video.tags && video.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                            {video.tags.slice(0, 3).map(tag => (
                                <span key={tag.id || tag.name} className="text-[10px] px-2 py-0.5 rounded-full bg-[#F5EDD8] text-[#B8922A] font-semibold">
                                    {tag.name}
                                </span>
                            ))}
                            {video.tags.length > 3 && <span className="text-[10px] text-[#A09890]">+{video.tags.length - 3}</span>}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};