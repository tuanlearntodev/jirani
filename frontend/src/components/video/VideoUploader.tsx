import { ChangeEvent } from 'react';
import { UploadCloud, Film, Loader2, X } from 'lucide-react';

interface VideoUploaderProps {
    files: File[];
    loading: boolean;
    alert: { msg: string; type: '' | 'success' | 'error' };
    onFileSelect: (e: ChangeEvent<HTMLInputElement>) => void;
    onRemoveFile: (index: number) => void;
    onUpload: () => void;
}

export const VideoUploader = ({ files, loading, alert, onFileSelect, onRemoveFile, onUpload }: VideoUploaderProps) => (
    <div className="relative bg-[#111111] border border-[#2a2a2a] border-t-2 border-t-[#C9A84C] rounded p-8 mb-12">
        <span className="absolute -top-2.5 left-6 bg-[#111111] px-2 font-mono text-[0.6rem] tracking-widest text-[#C9A84C] uppercase">
            Upload
        </span>

        <div className="relative bg-[#0A0A0A] border border-dashed border-[#2a2a2a] rounded-sm p-8 text-center cursor-pointer hover:border-[#7a5e20] hover:bg-[#0e0e0e] transition-colors mb-4">
            <input
                type="file"
                accept="video/*"
                multiple
                onChange={onFileSelect}
                className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
            />
            <Film className="mx-auto mb-2 text-[#4a4540]" size={24} />
            {files.length > 0
                ? <p className="font-mono text-xs text-[#E2C97E]">⬡ {files.length} file{files.length !== 1 ? 's' : ''} selected — click to change</p>
                : <p className="text-sm text-[#7a7265] font-light">Click or drag — select one or more videos</p>
            }
        </div>

        {files.length > 0 && (
            <div className="mb-4 border border-[#2a2a2a] rounded-sm overflow-hidden">
                {files.map((f, i) => (
                    <div key={i} className="flex items-center gap-3 px-3 py-2.5 border-b border-[#2a2a2a] last:border-b-0 bg-[#0d0d0d]">
                        <Film size={12} className="text-[#4a4540] flex-shrink-0" />
                        <span className="font-mono text-xs text-[#F0EAD6] truncate flex-1">{f.name}</span>
                        <span className="font-mono text-[0.6rem] text-[#4a4540] flex-shrink-0">
                            {(f.size / (1024 * 1024)).toFixed(1)} MB
                        </span>
                        <button onClick={() => onRemoveFile(i)} className="text-[#4a4540] hover:text-[#e07070] transition-colors flex-shrink-0">
                            <X size={12} />
                        </button>
                    </div>
                ))}
            </div>
        )}

        <button
            onClick={onUpload}
            disabled={loading || files.length === 0}
            className="w-full py-3 bg-[#C9A84C] text-[#0A0A0A] font-mono font-medium text-xs tracking-widest uppercase rounded-sm hover:bg-[#E2C97E] disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
        >
            {loading
                ? <><Loader2 size={14} className="animate-spin" /> Uploading...</>
                : <><UploadCloud size={14} /> Upload {files.length > 0 ? `(${files.length})` : ""}</>
            }
        </button>

        {alert.msg && (
            <div className={`mt-3 px-3 py-2.5 rounded-sm font-mono text-xs border ${alert.type === 'success'
                ? 'bg-[#0d1a0d] text-[#7ec87e] border-[#1e4020]'
                : 'bg-[#2a1210] text-[#e07070] border-[#4a1a18]'
                }`}>
                {alert.msg}
            </div>
        )}
    </div>
);