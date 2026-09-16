import { useState, ChangeEvent } from "react";
import { useAuth } from "../context/AuthContext";
import { useVideos } from "../hooks/useVideos";
import { VideoUploader } from "../components/video/VideoUploader";
import { VideoCard } from "../components/video/VideoCard";
import * as videosApi from "../api/videos";
import { Video as VideoType } from "../types";

type AlertType = "" | "success" | "error";

const UploadVideo = () => {
    const { isAdmin } = useAuth();
    const { videos, refresh, setVideos } = useVideos();

    const [files, setFiles] = useState<File[]>([]);
    const [alert, setAlert] = useState<{ msg: string; type: AlertType }>({ msg: "", type: "" });
    const [loading, setLoading] = useState(false);
    const [deletingId, setDeletingId] = useState<VideoType["id"] | null>(null);
    const [editingId, setEditingId] = useState<VideoType["id"] | null>(null);
    const [editTitle, setEditTitle] = useState("");
    const [editDescription, setEditDescription] = useState("");

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

    const upload = async () => {
        if (files.length === 0) { setAlert({ msg: "// no file selected", type: "error" }); return; }
        setLoading(true);
        try {
            files.length === 1 ? await videosApi.uploadVideo(files[0]) : await videosApi.uploadVideos(files);
            setAlert({ msg: `// ${files.length} video${files.length !== 1 ? "s" : ""} uploaded`, type: "success" });
            await refresh();
            setFiles([]);
        } catch {
            setAlert({ msg: "// upload failed — try again", type: "error" });
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async (id: VideoType["id"]) => {
        setDeletingId(id);
        try {
            await videosApi.deleteVideo(id);
            setVideos(prev => prev.filter(v => v.id !== id));
        } catch {
            setAlert({ msg: "// delete failed", type: "error" });
        } finally {
            setDeletingId(null);
        }
    };

    const saveEdit = async (id: VideoType["id"]) => {
        try {
            const updated = await videosApi.updateVideo(id, editTitle, editDescription);
            setVideos(prev => prev.map(v => v.id === id ? updated : v));
            setEditingId(null);
        } catch {
            setAlert({ msg: "// update failed", type: "error" });
        }
    };

    return (
        <>
            <VideoUploader
                files={files}
                loading={loading}
                alert={alert}
                onFileSelect={handleFileSelect}
                onRemoveFile={(i) => setFiles(prev => prev.filter((_, idx) => idx !== i))}
                onUpload={upload}
            />

            <div className="flex items-baseline gap-3 mb-4">
                <h2 className="font-serif text-xl font-semibold text-[#F0EAD6]">Library</h2>
                <span className="font-mono text-xs text-[#C9A84C]">{videos.length} video{videos.length !== 1 ? "s" : ""}</span>
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
                        <VideoCard
                            key={video.id}
                            video={video}
                            isEditing={editingId === video.id}
                            isDeleting={deletingId === video.id}
                            editTitle={editTitle}
                            editDescription={editDescription}
                            onEditTitleChange={setEditTitle}
                            onEditDescriptionChange={setEditDescription}
                            onStartEdit={() => { setEditingId(video.id); setEditTitle(video.title); setEditDescription(video.description || ""); }}
                            onSaveEdit={() => saveEdit(video.id)}
                            onCancelEdit={() => setEditingId(null)}
                            onDelete={() => handleDelete(video.id)}
                        />
                    ))}
                </div>
            )}
        </>
    );
};

export default UploadVideo;