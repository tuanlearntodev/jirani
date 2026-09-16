import { useState, ChangeEvent } from "react";
import { useAuth } from "../context/AuthContext";
import { useAudio } from "../hooks/useAudio";
import { AudioUploader } from "../components/audio/AudioUploader";
import { AudioCard } from "../components/audio/AudioCard";
import * as audioApi from "../api/audio";
import { Audio as AudioType } from "../types";

type AlertType = "" | "success" | "error";

const UploadAudio = () => {
    const { isAdmin } = useAuth();
    const { audioTracks, refresh, setAudioTracks } = useAudio();

    const [files, setFiles] = useState<File[]>([]);
    const [alert, setAlert] = useState<{ msg: string; type: AlertType }>({ msg: "", type: "" });
    const [loading, setLoading] = useState(false);
    const [deletingId, setDeletingId] = useState<AudioType["id"] | null>(null);
    const [editingId, setEditingId] = useState<AudioType["id"] | null>(null);
    const [editTitle, setEditTitle] = useState("");
    const [editDescription, setEditDescription] = useState("");
    const [currentlyPlayingId, setCurrentlyPlayingId] = useState<AudioType["id"] | null>(null);

    // Same server-side gap as video/book write routes — see /areas/jirani.md.
    // Client-side gate here is defense in depth until RoleChecker lands on /audio too.
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
            files.length === 1 ? await audioApi.uploadAudio(files[0]) : await audioApi.uploadAudioTracks(files);
            setAlert({ msg: `// ${files.length} track${files.length !== 1 ? "s" : ""} uploaded`, type: "success" });
            await refresh();
            setFiles([]);
        } catch {
            setAlert({ msg: "// upload failed — try again", type: "error" });
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async (id: AudioType["id"]) => {
        setDeletingId(id);
        try {
            await audioApi.deleteAudio(id);
            setAudioTracks(prev => prev.filter(a => a.id !== id));
        } catch {
            setAlert({ msg: "// delete failed", type: "error" });
        } finally {
            setDeletingId(null);
        }
    };

    const saveEdit = async (id: AudioType["id"]) => {
        try {
            const updated = await audioApi.updateAudio(id, editTitle, editDescription);
            setAudioTracks(prev => prev.map(a => a.id === id ? updated : a));
            setEditingId(null);
        } catch {
            setAlert({ msg: "// update failed", type: "error" });
        }
    };

    return (
        <>
            <AudioUploader
                files={files}
                loading={loading}
                alert={alert}
                onFileSelect={handleFileSelect}
                onRemoveFile={(i) => setFiles(prev => prev.filter((_, idx) => idx !== i))}
                onUpload={upload}
            />

            <div className="flex items-baseline gap-3 mb-4">
                <h2 className="font-serif text-xl font-semibold text-[#F0EAD6]">Library</h2>
                <span className="font-mono text-xs text-[#C9A84C]">{audioTracks.length} track{audioTracks.length !== 1 ? "s" : ""}</span>
            </div>
            <div className="relative h-px bg-[#2a2a2a] mb-6">
                <div className="absolute left-0 top-0 w-10 h-px bg-[#C9A84C]" />
            </div>

            {audioTracks.length === 0 ? (
                <div className="text-center py-16 border border-dashed border-[#2a2a2a] rounded">
                    <p className="font-mono text-xs text-[#4a4540]">// no audio in the archive yet</p>
                </div>
            ) : (
                <div className="grid grid-cols-[repeat(auto-fill,minmax(265px,1fr))] gap-5">
                    {audioTracks.map((audio) => (
                        <AudioCard
                            key={audio.id}
                            audio={audio}
                            isEditing={editingId === audio.id}
                            isDeleting={deletingId === audio.id}
                            editTitle={editTitle}
                            editDescription={editDescription}
                            currentlyPlayingId={currentlyPlayingId}
                            onPlay={setCurrentlyPlayingId}
                            onEditTitleChange={setEditTitle}
                            onEditDescriptionChange={setEditDescription}
                            onStartEdit={() => { setEditingId(audio.id); setEditTitle(audio.title); setEditDescription(audio.description || ""); }}
                            onSaveEdit={() => saveEdit(audio.id)}
                            onCancelEdit={() => setEditingId(null)}
                            onDelete={() => handleDelete(audio.id)}
                        />
                    ))}
                </div>
            )}
        </>
    );
};

export default UploadAudio;