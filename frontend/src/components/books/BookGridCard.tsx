import { useState, MouseEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { BookOpen, Loader2, Pencil, Trash2 } from 'lucide-react';
import { Book } from '../../types';
import API_BASE from '../../config';
import * as booksApi from '../../api/books';

interface BookGridCardProps {
    book: Book;
    isAdmin: boolean;
    onDelete: (uid: Book['uid']) => void;
    onEdit: (book: Book) => void;
}

export const BookGridCard = ({ book, isAdmin, onDelete, onEdit }: BookGridCardProps) => {
    const [deleting, setDeleting] = useState(false);
    const navigate = useNavigate();

    const handleDelete = async (e: MouseEvent) => {
        e.stopPropagation();
        setDeleting(true);
        try {
            await booksApi.deleteBook(book.uid);
            onDelete(book.uid);
        } finally {
            setDeleting(false);
        }
    };

    return (
        <div className="group bg-white rounded-2xl overflow-hidden border border-[#E8E4DE] shadow-[0_1px_4px_rgba(28,26,23,0.05)] hover:shadow-[0_10px_36px_rgba(28,26,23,0.11)] hover:-translate-y-[3px] transition-all flex flex-col">
            <div className="relative aspect-[2/3] bg-[#F7F5F2] overflow-hidden">
                {book.cover_url
                    ? <img src={`${API_BASE}${book.cover_url}`} alt={book.title} className="w-full h-full object-cover group-hover:scale-[1.04] transition-transform duration-300" />
                    : <div className="w-full h-full flex flex-col items-center justify-center gap-2 p-4">
                        <div className="w-11 h-11 rounded-xl bg-[#F5EDD8] flex items-center justify-center">
                            <BookOpen size={20} color="#B8922A" />
                        </div>
                        <span className="text-[11px] text-[#A09890] text-center leading-snug">{book.title}</span>
                    </div>
                }
                <div className="absolute top-2 left-2">
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wide ${book.extension === "epub" ? "bg-[#F0FAF4] text-[#2D7A4F]" : "bg-[#FEF2F0] text-[#D94F3D]"}`}>
                        {book.extension}
                    </span>
                </div>
                <div onClick={() => navigate(`/read/${book.uid}`)} className="absolute inset-0 cursor-pointer" />
                {isAdmin && (
                    <div className="absolute inset-0 bg-gradient-to-t from-[rgba(28,26,23,0.65)] to-transparent to-55% opacity-0 group-hover:opacity-100 transition-opacity flex items-end p-2.5 gap-1.5 justify-end pointer-events-none">
                        <button onClick={(e) => { e.stopPropagation(); onEdit(book); }}
                            className="w-[34px] h-[34px] rounded-[9px] bg-white/95 border-none cursor-pointer flex items-center justify-center text-[#6B6560] pointer-events-auto">
                            <Pencil size={14} />
                        </button>
                        <button onClick={handleDelete} disabled={deleting}
                            className="w-[34px] h-[34px] rounded-[9px] bg-white/95 border-none cursor-pointer flex items-center justify-center text-[#D94F3D] pointer-events-auto disabled:opacity-40">
                            {deleting ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
                        </button>
                    </div>
                )}
            </div>
            <div className="px-[13px] py-3 flex-1 flex flex-col gap-1.5">
                <span className="text-[13px] font-medium text-[#1C1A17] leading-snug line-clamp-2">
                    {book.title}
                </span>
                {book.tags && book.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                        {book.tags.slice(0, 3).map(tag => (
                            <span key={tag.id || tag.name} className="text-[10px] px-2 py-0.5 rounded-full bg-[#F5EDD8] text-[#B8922A] font-semibold">
                                {tag.name}
                            </span>
                        ))}
                        {book.tags.length > 3 && <span className="text-[10px] text-[#A09890]">+{book.tags.length - 3}</span>}
                    </div>
                )}
            </div>
        </div>
    );
};