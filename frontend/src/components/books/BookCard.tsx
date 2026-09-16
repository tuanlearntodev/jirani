import { Trash2, Loader2, Pencil, Check, X, FileText } from 'lucide-react';
import { Book } from '../../types';

interface BookCardProps {
    book: Book;
    isEditing: boolean;
    isDeleting: boolean;
    editTitle: string;
    onEditTitleChange: (v: string) => void;
    onStartEdit: () => void;
    onSaveEdit: () => void;
    onCancelEdit: () => void;
    onDelete: () => void;
    onRead: () => void;
}

export const BookCard = ({
    book, isEditing, isDeleting, editTitle,
    onEditTitleChange, onStartEdit, onSaveEdit, onCancelEdit, onDelete, onRead,
}: BookCardProps) => (
    <div className="bg-[#111111] border border-[#2a2a2a] rounded overflow-hidden hover:border-[#7a5e20] hover:-translate-y-0.5 transition-all duration-200">
        <button
            onClick={onRead}
            className="w-full h-44 bg-black flex items-center justify-center border-none cursor-pointer p-0"
        >
            {book.cover_url ? (
                <img src={book.cover_url} alt={book.title} className="w-full h-full object-cover" />
            ) : (
                <FileText size={32} className="text-[#4a4540]" />
            )}
        </button>

        {isEditing ? (
            <div className="px-3 py-3 border-t border-[#2a2a2a]">
                <input
                    autoFocus
                    value={editTitle}
                    onChange={(e) => onEditTitleChange(e.target.value)}
                    placeholder="Title..."
                    className="w-full bg-[#0A0A0A] border border-[#7a5e20] rounded-sm px-2 py-1.5 text-[#F0EAD6] text-sm outline-none mb-2"
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
            <div className="px-3 py-2.5 flex items-center justify-between gap-2 border-t border-[#2a2a2a]">
                <div className="flex flex-col min-w-0">
                    <span className="text-sm font-medium text-[#F0EAD6] truncate">{book.title}</span>
                    <span className="text-xs text-[#7a7265] uppercase">{book.extension}</span>
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