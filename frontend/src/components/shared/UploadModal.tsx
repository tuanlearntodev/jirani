import { useState, ChangeEvent } from 'react';
import { BookOpen, Film, Music, Upload, X, Loader2 } from 'lucide-react';
import * as booksApi from '../../services/api/books';
import * as videosApi from '../../services/api/videos';
import * as audioApi from '../../services/api/audio';

const inputStyle =
    "w-full px-3.5 py-2.5 border border-[#E8E4DE] rounded-[10px] text-[13px] text-[#1C1A17] bg-white outline-none box-border font-sans appearance-none [-webkit-text-fill-color:#1C1A17]";
const labelStyle = "text-xs text-[#6B6560] block mb-1.5 font-sans";

export type UploadKind = 'book' | 'audio' | 'video';

interface UploadModalProps {
    type: UploadKind;
    onClose: () => void;
    onSuccess: () => void;
}

export const UploadModal = ({ type, onClose, onSuccess }: UploadModalProps) => {
    const [files, setFiles] = useState<File[]>([]);
    const [tags, setTags] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const handleFileSelect = (e: ChangeEvent<HTMLInputElement>) => {
        setFiles(Array.from(e.target.files ?? []));
        e.target.value = '';
    };
    const removeFile = (i: number) => setFiles(prev => prev.filter((_, idx) => idx !== i));
    const acceptType = type === 'book' ? '.pdf,.epub' : type === 'audio' ? '.mp3,.wav,.ogg,.m4a,.aac,.flac' : 'video/*';

    const upload = async () => {
        if (files.length === 0) { setError('No files selected.'); return; }
        setLoading(true); setError('');
        try {
            if (type === 'book') {
                await booksApi.uploadBooks(files, tags);
            } else if (type === 'audio') {
                files.length === 1
                    ? await audioApi.uploadAudio(files[0], tags)
                    : await audioApi.uploadAudioTracks(files, tags);
            } else {
                files.length === 1
                    ? await videosApi.uploadVideo(files[0], tags)
                    : await videosApi.uploadVideos(files, tags);
            }
            onSuccess();
            onClose();
        } catch (e) {
            setError((e as Error).message || 'Upload failed.');
        } finally {
            setLoading(false);
        }
    };

    const TabIcon = type === 'book' ? BookOpen : type === 'audio' ? Music : Film;
    const tabLabel = type === 'book' ? 'Add Book' : type === 'audio' ? 'Add Audio' : 'Add Video';

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#1C1A17]/40 backdrop-blur-sm">
            <div className="bg-white rounded-[20px] w-full max-w-[440px] mx-4 shadow-[0_32px_80px_rgba(28,26,23,0.18)] overflow-hidden">
                <div className="px-6 pt-5.5 flex items-center justify-between">
                    <span className="text-[19px] font-bold text-[#1C1A17]">{tabLabel}</span>
                    <button onClick={onClose} className="w-[34px] h-[34px] rounded-[10px] border border-[#E8E4DE] bg-[#F7F5F2] flex items-center justify-center cursor-pointer text-[#6B6560]">
                        <X size={15} />
                    </button>
                </div>
                <div className="p-6 flex flex-col gap-3">
                    <div className="relative bg-[#FAFAF9] border-2 border-dashed border-[#D4CFC8] rounded-2xl py-7 px-5 text-center cursor-pointer">
                        <input type="file" accept={acceptType} multiple onChange={handleFileSelect}
                            className="absolute inset-0 opacity-0 cursor-pointer w-full h-full" />
                        <div className="w-11 h-11 rounded-xl bg-[#F5EDD8] flex items-center justify-center mx-auto mb-2.5">
                            <TabIcon size={18} color="#B8922A" />
                        </div>
                        {files.length > 0
                            ? <p className="text-[13px] text-[#B8922A] font-medium m-0">{files.length} file{files.length !== 1 ? "s" : ""} selected</p>
                            : <>
                                <p className="text-[13px] text-[#1C1A17] font-medium mb-0.5">Click to browse</p>
                                <p className="text-xs text-[#A09890] m-0">
                                    {type === "book" ? "PDF or EPUB" : type === "audio" ? "MP3, WAV, OGG, M4A, AAC, FLAC" : "Video files"}
                                </p>
                            </>
                        }
                    </div>

                    {files.length > 0 && (
                        <div className="border border-[#E8E4DE] rounded-xl overflow-hidden max-h-[140px] overflow-y-auto">
                            {files.map((f, i) => (
                                <div key={i} className={`flex items-center gap-2.5 px-3.5 py-2.5 ${i < files.length - 1 ? "border-b border-[#E8E4DE]" : ""}`}>
                                    <span className="text-[11px] text-[#1C1A17] flex-1 overflow-hidden text-ellipsis whitespace-nowrap">{f.name}</span>
                                    <span className="font-mono text-[10px] text-[#A09890] flex-shrink-0">{(f.size / (1024 * 1024)).toFixed(1)} MB</span>
                                    <button onClick={() => removeFile(i)} className="bg-transparent border-none cursor-pointer text-[#A09890] p-0 flex"><X size={12} /></button>
                                </div>
                            ))}
                        </div>
                    )}

                    <div>
                        <label className={labelStyle}>Tags (optional, comma separated)</label>
                        <input
                            type="text"
                            placeholder="history, science, fiction..."
                            value={tags}
                            onChange={e => setTags(e.target.value)}
                            className={inputStyle}
                        />
                    </div>

                    {error && <p className="m-0 text-xs text-[#A09890] text-center">{error}</p>}

                    <button onClick={upload} disabled={loading || files.length === 0}
                        className={`py-3.5 rounded-xl text-sm font-semibold flex items-center justify-center gap-2 ${files.length === 0 || loading ? "bg-[#E8E4DE] text-[#A09890] cursor-not-allowed" : "bg-[#B8922A] text-white cursor-pointer"}`}>
                        {loading ? <><Loader2 size={14} className="animate-spin" /> Uploading...</> : <><Upload size={14} /> Upload</>}
                    </button>
                </div>
            </div>
        </div>
    );
};