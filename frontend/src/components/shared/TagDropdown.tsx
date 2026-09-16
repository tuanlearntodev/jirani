import { useState, useEffect, useRef } from 'react';
import { Tag, Check, X } from 'lucide-react';
import { Tag as TagType } from '../../types';

const inputStyle =
    "w-full px-3.5 py-2.5 border border-[#E8E4DE] rounded-[10px] text-[13px] text-[#1C1A17] bg-white outline-none box-border font-sans appearance-none [-webkit-text-fill-color:#1C1A17]";

interface TagDropdownProps {
    allTags: TagType[];
    selectedTags: string[];
    onToggle: (tag: string) => void;
    onClear: () => void;
}

export const TagDropdown = ({ allTags, selectedTags, onToggle, onClear }: TagDropdownProps) => {
    const [open, setOpen] = useState(false);
    const [tagSearch, setTagSearch] = useState('');
    const ref = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const handler = (e: MouseEvent) => {
            if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, []);

    const filtered = allTags.filter(t => t.name.toLowerCase().includes(tagSearch.toLowerCase()));

    return (
        <div ref={ref} className="relative">
            <button onClick={() => setOpen(p => !p)}
                className={`flex items-center gap-1.5 px-3.5 py-2 rounded-[10px] text-[13px] cursor-pointer whitespace-nowrap ${selectedTags.length > 0 ? "bg-[#F5EDD8] border-[1.5px] border-[#B8922A] text-[#B8922A]" : "bg-[#F7F5F2] border border-[#E8E4DE] text-[#6B6560]"}`}>
                <Tag size={13} />
                {selectedTags.length > 0 ? `${selectedTags.length}` : ""}
                <span className="text-[10px] ml-0.5">{open ? "▲" : "▼"}</span>
            </button>

            {open && (
                <div className="absolute top-[calc(100%+6px)] right-0 z-[100] bg-white border border-[#E8E4DE] rounded-xl shadow-[0_8px_32px_rgba(28,26,23,0.12)] min-w-[200px] overflow-hidden">
                    <div className="px-3 py-2.5 border-b border-[#E8E4DE]">
                        <input
                            autoFocus
                            value={tagSearch}
                            onChange={e => setTagSearch(e.target.value)}
                            placeholder="Search tags..."
                            className={`${inputStyle} px-2.5 py-1.5 text-xs`}
                        />
                    </div>
                    <div className="max-h-[220px] overflow-y-auto">
                        {filtered.length === 0
                            ? <p className="px-3.5 py-3 text-xs text-[#A09890] m-0">No tags found</p>
                            : filtered.map(tag => {
                                const active = selectedTags.includes(tag.name);
                                return (
                                    <button key={tag.id} onClick={() => onToggle(tag.name)}
                                        className={`w-full text-left px-3.5 py-2.5 border-none cursor-pointer text-[13px] flex items-center justify-between ${active ? "bg-[#F5EDD8] text-[#B8922A] font-semibold" : "bg-transparent text-[#1C1A17] font-normal"}`}>
                                        {tag.name}
                                        {active && <Check size={12} color="#B8922A" />}
                                    </button>
                                );
                            })
                        }
                    </div>
                    {selectedTags.length > 0 && (
                        <div className="px-3 py-2 border-t border-[#E8E4DE]">
                            <button onClick={() => { onClear(); setOpen(false); }}
                                className="w-full py-1.5 bg-[#F7F5F2] border border-[#E8E4DE] rounded-lg text-xs text-[#A09890] cursor-pointer flex items-center justify-center gap-1.5">
                                <X size={10} /> Clear all
                            </button>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};