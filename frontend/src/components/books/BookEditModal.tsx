import { useState } from 'react';
import { Check, Loader2, X } from 'lucide-react';
import { Book } from '../../types';
import * as booksApi from '../../api/books';

const inputStyle =
    "w-full px-3.5 py-2.5 border border-[#E8E4DE] rounded-[10px] text-[13px] text-[#1C1A17] bg-white outline-none box-border font-sans appearance-none [-webkit-text-fill-color:#1C1A17]";
const labelStyle = "text-xs text-[#6B6560] block mb-1.5 font-sans";

interface BookEditModalProps {
    book: Book;
    onClose: () => void;
    onUpdate: (updated: Book) => void;
}

export const BookEditModal = ({ book, onClose, onUpdate }: BookEditModalProps) => {
    const [title, setTitle] = useState(book.title || '');
    const [tags, setTags] = useState(book.tags?.map(t => t.name).join(', ') || '');
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');

    const save = async () => {
        setSaving(true); setError('');
        try {
            const updated = await booksApi.updateBook(book.uid, title, tags);
            onUpdate(updated);
            onClose();
        } catch (e) {
            setError((e as Error).message || 'Failed to save.');
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#1C1A17]/40 backdrop-blur-sm">
            <div className="bg-white rounded-[20px] w-full max-w-[420px] mx-4 shadow-[0_32px_80px_rgba(28,26,23,0.18)] overflow-hidden">
                <div className="px-6 pt-5.5 flex items-center justify-between">
                    <span className="text-[19px] font-bold text-[#1C1A17]">Edit Book</span>
                    <button onClick={onClose} className="w-[34px] h-[34px] rounded-[10px] border border-[#E8E4DE] bg-[#F7F5F2] flex items-center justify-center cursor-pointer text-[#6B6560]">
                        <X size={15} />
                    </button>
                </div>
                <div className="p-6 flex flex-col gap-3.5">
                    <div>
                        <label className={labelStyle}>Title</label>
                        <input value={title} onChange={e => setTitle(e.target.value)} placeholder="Book title..." className={inputStyle} />
                    </div>
                    <div>
                        <label className={labelStyle}>Tags (comma separated)</label>
                        <input value={tags} onChange={e => setTags(e.target.value)} placeholder="history, science, fiction..." className={inputStyle} />
                    </div>
                    {error && <p className="m-0 text-xs text-[#A09890] text-center">{error}</p>}
                    <div className="flex gap-2">
                        <button onClick={save} disabled={saving}
                            className={`flex-1 py-3 rounded-[10px] text-[13px] font-semibold flex items-center justify-center gap-1.5 ${saving ? "bg-[#E8E4DE] text-[#A09890] cursor-not-allowed" : "bg-[#B8922A] text-white cursor-pointer"}`}>
                            {saving ? <><Loader2 size={13} className="animate-spin" /> Saving...</> : <><Check size={13} /> Save</>}
                        </button>
                        <button onClick={onClose} className="flex-1 py-3 bg-[#F7F5F2] text-[#6B6560] border border-[#E8E4DE] rounded-[10px] text-[13px] cursor-pointer">
                            Cancel
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};