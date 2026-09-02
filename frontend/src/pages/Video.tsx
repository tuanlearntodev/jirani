import { useState, useEffect, ChangeEvent } from "react";
import { Trash2, Loader2, UploadCloud, Film, Pencil, Check, X } from "lucide-react";
import API_BASE from '../config';
import { useAuth } from "../context/AuthContext";
import { Video as VideoType } from "../types";

type AlertType = "" | "success" | "error";

const UploadVideo = () => {
    const { isAdmin } = useAuth();

    const [files, setFiles] = useState<File[]>([]);
    const [alert, setAlert] = useState<{ msg: string; type: AlertType }>({ msg: "", type: "" });
    const [loading, setLoading] = useState<boolean>(false);
    const [videos, setVideos] = useState<VideoType[]>([]);
    const [deletingId, setDeletingId] = useState<VideoType["id"] | null>(null);

    // Inline edit state
    const [editingId, setEditingId] = useState<VideoType["id"] | null>(null);
    const [editTitle, setEditTitle] = useState<string>("");
    const [editDescription, setEditDescription] = useState<string>("");

    const getVideos = async () => {
        const res = await fetch(`${API_BASE}/videos`);
        setVideos(await res.json());
    };

    useEffect(() => { getVideos(); }, []);

    // This page performs uploads/edits/deletes with no backend auth check today
    // (see /areas/jirani.md: RoleChecker missing on video/audio/book write routes).
    // Gate the UI here as defense in depth until that's fixed server-side.
    if (!isAdmin) {
        return (
            <div className="max-w-xl mx-auto py-24 text-center">
                <p className="font-mono text-sm text-[#7a7265]">// admin access required</p>
            </div>
        );
    }

    const handleFileSelect = (e: ChangeEvent<HTMLInputElement>) => {
        setFiles(Array.from(e.target.files ?? []));
        e.target.value = "";
    };

    const removeFile = (index: number) => {
        setFiles(prev => prev.filter((_, i) => i !== index));
    };

    const upload = async () => {
        if (files.length === 0) {
            setAlert({ msg: "// no file selected", type: "error" });
            return;
        }

        setLoading(true);
        try {
            if (files.length === 1) {
                const formData = new FormData();
                formData.append("file", files[0]);
                formData.append("title", files[0].name.replace(/\.[^/.]+$/, ""));
                const res = await fetch(`${API_BASE}/videos/upload`, { method: "POST", body: formData });
                if (!res.ok) throw new Error();
            } else {
                const formData = new FormData();
                files.forEach(f => formData.append("files", f));
                const res = await fetch(`${API_BASE}/videos/upload_multiple`, { method: "POST", body: formData });
                if (!res.ok) throw new Error();
            }

            setAlert({ msg: `// ${files.length} video${files.length !== 1 ? "s" : ""} uploaded`, type: "success" });
            getVideos();
            setFiles([]);
        } catch {
            setAlert({ msg: "// upload failed — try again", type: "error" });
        } finally {
            setLoading(false);
        }
    };

    const deleteVideo = async (id: VideoType["id"]) => {
        setDeletingId(id);
        try {
            const res = await fetch(`${API_BASE}/videos/${id}`, { method: "DELETE" });
            if (!res.ok) throw new Error();
            setVideos(prev => prev.filter((v) => v.id !== id));
        } catch {
            setAlert({ msg: "// delete failed", type: "error" });
        } finally {
            setDeletingId(null);
        }
    };

    const startEditing = (video: VideoType) => {
        setEditingId(video.id);
        setEditTitle(video.title);
        setEditDescription(video.description || "");
    };

    const cancelEditing = () => {
        setEditingId(null);
        setEditTitle("");
        setEditDescription("");
    };

    const saveEdit = async (id: VideoType["id"]) => {
        try {
            const params = new URLSearchParams();
            if (editTitle.trim()) params.append("title", editTitle.trim());
            params.append("description", editDescription);
            const res = await fetch(`${API_BASE}/videos/${id}?${params}`, { method: "PATCH" });
            if (!res.ok) throw new Error();
            const updated = await res.json();
            setVideos(prev => prev.map(v => v.id === id ? updated : v));
            cancelEditing();
        } catch {
            setAlert({ msg: "// update failed", type: "error" });
        }
    };

    return (
        <>
            {/* Upload Card */}
            <div className="relative bg-[#111111] border border-[#2a2a2a] border-t-2 border-t-[#C9A84C] rounded p-8 mb-12">
                <span className="absolute -top-2.5 left-6 bg-[#111111] px-2 font-mono text-[0.6rem] tracking-widest text-[#C9A84C] uppercase">
                    Upload
                </span>

                {/* File picker dropzone */}
                <div className="relative bg-[#0A0A0A] border border-dashed border-[#2a2a2a] rounded-sm p-8 text-center cursor-pointer hover:border-[#7a5e20] hover:bg-[#0e0e0e] transition-colors mb-4">
                    <input
                        type="file"
                        accept="video/*"
                        multiple
                        onChange={handleFileSelect}
                        className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
                    />
                    <Film className="mx-auto mb-2 text-[#4a4540]" size={24} />
                    {files.length > 0
                        ? <p className="font-mono text-xs text-[#E2C97E]">⬡ {files.length} file{files.length !== 1 ? "s" : ""} selected — click to change</p>
                        : <p className="text-sm text-[#7a7265] font-light">Click or drag — select one or more videos</p>
                    }
                </div>

                {/* Selected file list */}
                {files.length > 0 && (
                    <div className="mb-4 border border-[#2a2a2a] rounded-sm overflow-hidden">
                        {files.map((f, i) => (
                            <div key={i} className="flex items-center gap-3 px-3 py-2.5 border-b border-[#2a2a2a] last:border-b-0 bg-[#0d0d0d]">
                                <Film size={12} className="text-[#4a4540] flex-shrink-0" />
                                <span className="font-mono text-xs text-[#F0EAD6] truncate flex-1">{f.name}</span>
                                <span className="font-mono text-[0.6rem] text-[#4a4540] flex-shrink-0">
                                    {(f.size / (1024 * 1024)).toFixed(1)} MB
                                </span>
                                <button onClick={() => removeFile(i)} className="text-[#4a4540] hover:text-[#e07070] transition-colors flex-shrink-0">
                                    <X size={12} />
                                </button>
                            </div>
                        ))}
                    </div>
                )}

                <button
                    onClick={upload}
                    disabled={loading || files.length === 0}
                    className="w-full py-3 bg-[#C9A84C] text-[#0A0A0A] font-mono font-medium text-xs tracking-widest uppercase rounded-sm hover:bg-[#E2C97E] disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
                >
                    {loading
                        ? <><Loader2 size={14} className="animate-spin" /> Uploading...</>
                        : <><UploadCloud size={14} /> Upload {files.length > 0 ? `(${files.length})` : ""}</>
                    }
                </button>

                {alert.msg && (
                    <div className={`mt-3 px-3 py-2.5 rounded-sm font-mono text-xs border ${alert.type === "success"
                            ? "bg-[#0d1a0d] text-[#7ec87e] border-[#1e4020]"
                            : "bg-[#2a1210] text-[#e07070] border-[#4a1a18]"
                        }`}>
                        {alert.msg}
                    </div>
                )}
            </div>

            {/* Library Header */}
            <div className="flex items-baseline gap-3 mb-4">
                <h2 className="font-serif text-xl font-semibold text-[#F0EAD6]">Library</h2>
                <span className="font-mono text-xs text-[#C9A84C]">
                    {videos.length} video{videos.length !== 1 ? "s" : ""}
                </span>
            </div>
            <div className="relative h-px bg-[#2a2a2a] mb-6">
                <div className="absolute left-0 top-0 w-10 h-px bg-[#C9A84C]" />
            </div>

            {videos.length === 0 ? (
                <div className="text-center py-16 border border-dashed border-[#2a2a2a] rounded">
                    <p className="font-mono text-xs text-[#4a4540]">// no videos in the archive yet</p>
                </div>
            ) : (
                <div className="grid grid-cols-[repeat(auto-fill,minmax(265px,1fr))] gap-5">
                    {videos.map((video) => (
                        <div
                            key={video.id}
                            className="bg-[#111111] border border-[#2a2a2a] rounded overflow-hidden hover:border-[#7a5e20] hover:-translate-y-0.5 transition-all duration-200"
                        >
                            <video controls preload="metadata" className="w-full block bg-black max-h-44 object-cover">
                                <source src={`${API_BASE}/videos/stream/${video.id}`} type="video/mp4" />
                            </video>

                            {editingId === video.id ? (
                                <div className="px-3 py-3 border-t border-[#2a2a2a]">
                                    <input
                                        autoFocus
                                        value={editTitle}
                                        onChange={(e) => setEditTitle(e.target.value)}
                                        placeholder="Title..."
                                        className="w-full bg-[#0A0A0A] border border-[#7a5e20] rounded-sm px-2 py-1.5 text-[#F0EAD6] text-sm outline-none mb-1.5"
                                    />
                                    <input
                                        value={editDescription}
                                        onChange={(e) => setEditDescription(e.target.value)}
                                        placeholder="Description (optional)..."
                                        className="w-full bg-[#0A0A0A] border border-[#2a2a2a] rounded-sm px-2 py-1.5 text-[#7a7265] text-xs outline-none focus:border-[#7a5e20] transition-colors mb-2"
                                    />
                                    <div className="flex gap-2">
                                        <button
                                            onClick={() => saveEdit(video.id)}
                                            className="flex-1 py-1.5 bg-[#C9A84C] text-[#0A0A0A] font-mono text-[0.6rem] tracking-widest uppercase rounded-sm hover:bg-[#E2C97E] transition-colors flex items-center justify-center gap-1"
                                        >
                                            <Check size={10} /> Save
                                        </button>
                                        <button
                                            onClick={cancelEditing}
                                            className="flex-1 py-1.5 border border-[#2a2a2a] text-[#7a7265] font-mono text-[0.6rem] tracking-widest uppercase rounded-sm hover:border-[#4a4540] transition-colors flex items-center justify-center gap-1"
                                        >
                                            <X size={10} /> Cancel
                                        </button>
                                    </div>
                                </div>
                            ) : (
                                <div className="px-3 py-2.5 flex items-center justify-between gap-2 border-t border-[#2a2a2a]">
                                    <div className="flex flex-col min-w-0">
                                        <span className="text-sm font-medium text-[#F0EAD6] truncate">{video.title}</span>
                                        {video.description && (
                                            <span className="text-xs text-[#7a7265] truncate">{video.description}</span>
                                        )}
                                    </div>
                                    <div className="flex gap-1 flex-shrink-0">
                                        <button
                                            title="Edit"
                                            onClick={() => startEditing(video)}
                                            className="w-8 h-8 flex items-center justify-center border border-[#2a2a2a] rounded-sm text-[#4a4540] hover:bg-[#1a1a0a] hover:border-[#7a5e20] hover:text-[#C9A84C] transition-colors"
                                        >
                                            <Pencil size={12} />
                                        </button>
                                        <button
                                            title="Delete"
                                            disabled={deletingId === video.id}
                                            onClick={() => deleteVideo(video.id)}
                                            className="w-8 h-8 flex items-center justify-center border border-[#2a2a2a] rounded-sm text-[#4a4540] hover:bg-[#2a1210] hover:border-[#c0392b] hover:text-[#e07070] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                                        >
                                            {deletingId === video.id
                                                ? <Loader2 size={13} className="animate-spin text-[#e07070]" />
                                                : <Trash2 size={13} />
                                            }
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </>
    );
};

export default UploadVideo;