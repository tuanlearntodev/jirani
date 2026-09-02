import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import {
    BookOpen, Film, Upload, Search, Music, LogOut, UserPlus, Loader2,
} from "lucide-react";

import { Book, Video, Audio, Tag as TagType } from "../types";
import * as booksApi from "../services/api/books";
import { useVideos } from "../hooks/useVideos";
import { useAudio } from "../hooks/useAudio";
import { useBookSearch } from "../hooks/useBookSearch";

import { TagDropdown } from "../components/shared/TagDropdown";
import { EmptyState } from "../components/shared/EmptyState";
import { UploadModal, UploadKind } from "../components/shared/UploadModal";
import { AddAdminModal } from "../components/auth/AddAdminModal";
import { BookEditModal } from "../components/books/BookEditModal";
import { BookGridCard } from "../components/books/BookGridCard";
import { VideoGridCard } from "../components/video/VideoGridCard";
import { VideoPlayerModal } from "../components/video/VideoPlayerModal";
import { AudioGridCard } from "../components/audio/AudioGridCard";

type TabId = "books" | "audio" | "videos";

const uniqueTags = (items: { tags?: TagType[] }[]): TagType[] => [
    ...new Map(items.flatMap(item => item.tags || []).map(tag => [tag.name, tag])).values(),
];

const Library = () => {
    const { isAdmin, logout, auth } = useAuth();
    const navigate = useNavigate();

    const isMobile = window.innerWidth < 640;

    const [activeTab, setActiveTab] = useState<TabId>("books");
    const [search, setSearch] = useState("");
    const [selectedBookTags, setSelectedBookTags] = useState<string[]>([]);
    const [selectedVideoTags, setSelectedVideoTags] = useState<string[]>([]);
    const [selectedAudioTags, setSelectedAudioTags] = useState<string[]>([]);
    const [showUpload, setShowUpload] = useState(false);
    const [editingBook, setEditingBook] = useState<Book | null>(null);
    const [currentlyPlayingAudio, setCurrentlyPlayingAudio] = useState<Audio["id"] | null>(null);
    const [playingVideo, setPlayingVideo] = useState<Video | null>(null);
    const [showAddAdmin, setShowAddAdmin] = useState(false);

    // Books support real server-side search/tag filtering.
    const { books, refresh: refreshBooks, setBooks } = useBookSearch(selectedBookTags, search);
    // Videos/audio have no search endpoint — fetch the full list, filter client-side below.
    const { videos, refresh: refreshVideos, setVideos } = useVideos();
    const { audioTracks, refresh: refreshAudio, setAudioTracks } = useAudio();

    // Unique book tags come from the unfiltered set, so they don't shrink as filters narrow the list.
    const [bookTagsList, setBookTagsList] = useState<TagType[]>([]);
    const refreshBookTags = async () => {
        const all = await booksApi.searchBooks();
        setBookTagsList(uniqueTags(all));
    };

    const [loading, setLoading] = useState(true);
    useEffect(() => {
        // The hooks above already fetch on mount; this just tracks combined
        // loading state and pulls the unfiltered tag list once.
        Promise.all([refreshBooks(), refreshVideos(), refreshAudio(), refreshBookTags()])
            .finally(() => setLoading(false));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const filteredVideos = useMemo(() => videos.filter(v =>
        v.title.toLowerCase().includes(search.toLowerCase()) &&
        (selectedVideoTags.length === 0 || v.tags?.some(t => selectedVideoTags.includes(t.name)))
    ), [videos, search, selectedVideoTags]);

    const filteredAudio = useMemo(() => audioTracks.filter(a =>
        a.title.toLowerCase().includes(search.toLowerCase()) &&
        (selectedAudioTags.length === 0 || a.tags?.some(t => selectedAudioTags.includes(t.name)))
    ), [audioTracks, search, selectedAudioTags]);

    const videoTagsList = useMemo(() => uniqueTags(videos), [videos]);
    const audioTagsList = useMemo(() => uniqueTags(audioTracks), [audioTracks]);

    const handleLogout = () => { logout(); navigate("/"); };
    const uploadType: UploadKind = activeTab === "books" ? "book" : activeTab === "audio" ? "audio" : "video";

    const tabs: { id: TabId; label: string; icon: typeof BookOpen; count: number }[] = [
        { id: "books", label: "Books", icon: BookOpen, count: books.length },
        { id: "audio", label: "Audio", icon: Music, count: audioTracks.length },
        { id: "videos", label: "Videos", icon: Film, count: videos.length },
    ];

    return (
        <div className="flex h-screen bg-white font-sans overflow-hidden">

            {/* SIDEBAR */}
            <aside className={`${isMobile ? "w-[58px]" : "w-[220px]"} flex-shrink-0 bg-white border-r border-[#E8E4DE] flex flex-col`}>
                <div className={`${isMobile ? "py-3.5 justify-center" : "pt-6 px-5 pb-5 justify-start"} border-b border-[#E8E4DE] flex items-center`}>
                    {isMobile
                        ? <BookOpen size={20} color="#B8922A" />
                        : <div>
                            <h1 className="text-[21px] font-bold text-[#1C1A17] m-0 tracking-[-0.01em]">Jirani</h1>
                            <p className="text-[10px] text-[#A09890] mt-1 mb-0 uppercase tracking-[0.08em] font-semibold">Offline Library</p>
                        </div>
                    }
                </div>

                <nav className={isMobile ? "py-2.5 px-1.5" : "py-3 px-2.5"}>
                    {tabs.map(({ id, label, icon: Icon, count }) => (
                        <button key={id}
                            onClick={() => { setActiveTab(id); setSelectedBookTags([]); setSelectedVideoTags([]); setSelectedAudioTags([]); setSearch(""); }}
                            className={`w-full flex items-center ${isMobile ? "justify-center flex-col gap-0.5 py-2" : "justify-between flex-row gap-2 py-2.5 px-3"} rounded-[10px] border-none cursor-pointer mb-0.5 text-[13px] transition-colors ${activeTab === id ? "bg-[#F5EDD8] text-[#B8922A] font-bold" : "bg-transparent text-[#6B6560] font-normal"}`}>
                            {isMobile
                                ? <>
                                    <Icon size={20} />
                                    <span className={`text-[9px] font-semibold ${activeTab === id ? "text-[#B8922A]" : "text-[#A09890]"}`}>{count}</span>
                                </>
                                : <>
                                    <div className="flex items-center gap-2">
                                        <Icon size={15} />
                                        <span>{label}</span>
                                    </div>
                                    <span className={`text-[11px] px-2 py-0.5 rounded-full font-semibold ${activeTab === id ? "bg-[#B8922A] text-white" : "bg-[#F0EDE8] text-[#A09890]"}`}>
                                        {count}
                                    </span>
                                </>
                            }
                        </button>
                    ))}
                </nav>

                <div className={`mt-auto ${isMobile ? "py-2.5 px-1.5" : "py-3 px-2.5"} border-t border-[#E8E4DE] flex flex-col gap-1.5`}>
                    {isAdmin && (
                        <button onClick={() => setShowAddAdmin(true)}
                            className={`w-full flex items-center ${isMobile ? "justify-center py-2" : "justify-start py-2 px-3"} gap-2 rounded-[10px] border border-dashed border-[#D4A93A] bg-transparent hover:bg-[#F5EDD8] text-[#B8922A] cursor-pointer text-xs font-semibold transition-colors`}>
                            <UserPlus size={isMobile ? 18 : 13} />
                            {!isMobile && "Add Admin"}
                        </button>
                    )}
                    <div className={`${isMobile ? "py-2 justify-center" : "py-2 px-3 justify-between"} rounded-[10px] bg-[#FAFAF9] flex items-center gap-2`}>
                        {!isMobile && (
                            <div className="min-w-0">
                                <p className="text-xs font-semibold text-[#1C1A17] m-0 overflow-hidden text-ellipsis whitespace-nowrap">
                                    {isAdmin ? auth?.username : "Student"}
                                </p>
                                <p className="text-[10px] text-[#A09890] m-0 uppercase font-semibold">
                                    {isAdmin ? "Admin" : "Guest"}
                                </p>
                            </div>
                        )}
                        <button onClick={handleLogout} title="Sign out"
                            className="w-[30px] h-[30px] rounded-lg border border-[#E8E4DE] bg-white cursor-pointer flex items-center justify-center text-[#A09890] flex-shrink-0">
                            <LogOut size={13} />
                        </button>
                    </div>
                </div>
            </aside>

            {/* MAIN */}
            <main className="flex-1 flex flex-col min-w-0 bg-[#FAFAF9]">

                {/* Topbar */}
                <div className={`flex items-center gap-2 ${isMobile ? "px-3 py-3" : "px-7 py-4"} bg-white border-b border-[#E8E4DE]`}>
                    <h2 className={`${isMobile ? "text-base" : "text-[22px]"} font-bold text-[#1C1A17] m-0 tracking-[-0.01em] flex-shrink-0`}>
                        {activeTab === "books" ? "Books" : activeTab === "audio" ? "Audio" : "Videos"}
                    </h2>
                    <span className="text-[11px] px-2.5 py-0.5 rounded-full bg-[#F5EDD8] text-[#B8922A] flex-shrink-0 font-semibold">
                        {activeTab === "books" ? books.length : activeTab === "audio" ? filteredAudio.length : filteredVideos.length}
                    </span>

                    <div className="ml-auto flex items-center gap-1.5">
                        <div className={`flex items-center gap-1.5 bg-[#F7F5F2] border border-[#E8E4DE] rounded-[10px] px-2.5 py-2 min-w-0 flex-1 ${isMobile ? "max-w-[140px]" : "max-w-[220px]"}`}>
                            <Search size={13} color="#A09890" className="flex-shrink-0" />
                            <input
                                type="text"
                                placeholder="Search..."
                                value={search}
                                onChange={e => setSearch(e.target.value)}
                                className="border-none outline-none text-[13px] text-[#1C1A17] [-webkit-text-fill-color:#1C1A17] bg-transparent w-full min-w-0 p-0 appearance-none"
                            />
                        </div>

                        {activeTab === "books" && (
                            <TagDropdown allTags={bookTagsList} selectedTags={selectedBookTags}
                                onToggle={tag => setSelectedBookTags(prev => prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag])}
                                onClear={() => setSelectedBookTags([])} />
                        )}
                        {activeTab === "videos" && (
                            <TagDropdown allTags={videoTagsList} selectedTags={selectedVideoTags}
                                onToggle={tag => setSelectedVideoTags(prev => prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag])}
                                onClear={() => setSelectedVideoTags([])} />
                        )}
                        {activeTab === "audio" && (
                            <TagDropdown allTags={audioTagsList} selectedTags={selectedAudioTags}
                                onToggle={tag => setSelectedAudioTags(prev => prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag])}
                                onClear={() => setSelectedAudioTags([])} />
                        )}

                        {isAdmin && (
                            <button onClick={() => setShowUpload(true)}
                                className={`flex items-center ${isMobile ? "gap-0 px-2.5 py-2" : "gap-1.5 px-4 py-2"} bg-white hover:bg-[#F5EDD8] border-[1.5px] border-[#B8922A] rounded-[10px] text-[13px] font-semibold text-[#B8922A] cursor-pointer transition-colors whitespace-nowrap flex-shrink-0`}>
                                <Upload size={13} />
                                {!isMobile && ` Upload ${activeTab === "books" ? "Book" : activeTab === "audio" ? "Audio" : "Video"}`}
                            </button>
                        )}
                    </div>
                </div>

                {/* Grid */}
                <div className={`flex-1 overflow-y-auto ${isMobile ? "p-3" : "p-6"}`}>
                    {loading ? (
                        <div className="flex items-center justify-center h-full">
                            <Loader2 size={26} color="#B8922A" className="animate-spin" />
                        </div>
                    ) : activeTab === "books" ? (
                        books.length === 0
                            ? <EmptyState icon={BookOpen} label="books" onUpload={() => setShowUpload(true)} isAdmin={isAdmin} />
                            : <div className={`grid grid-cols-[repeat(auto-fill,minmax(130px,1fr))] ${isMobile ? "gap-2.5" : "gap-4"}`}>
                                {books.map(book => (
                                    <BookGridCard key={book.uid} book={book} isAdmin={isAdmin}
                                        onDelete={uid => setBooks(prev => prev.filter(b => b.uid !== uid))}
                                        onEdit={setEditingBook} />
                                ))}
                            </div>
                    ) : activeTab === "audio" ? (
                        filteredAudio.length === 0
                            ? <EmptyState icon={Music} label="audio" onUpload={() => setShowUpload(true)} isAdmin={isAdmin} />
                            : <div className={`grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] ${isMobile ? "gap-2.5" : "gap-4"}`}>
                                {filteredAudio.map(audio => (
                                    <AudioGridCard key={audio.id} audio={audio} isAdmin={isAdmin}
                                        onPlay={setCurrentlyPlayingAudio}
                                        currentlyPlaying={currentlyPlayingAudio}
                                        onDelete={id => setAudioTracks(prev => prev.filter(a => a.id !== id))}
                                        onUpdate={updated => setAudioTracks(prev => prev.map(a => a.id === updated.id ? updated : a))} />
                                ))}
                            </div>
                    ) : (
                        filteredVideos.length === 0
                            ? <EmptyState icon={Film} label="videos" onUpload={() => setShowUpload(true)} isAdmin={isAdmin} />
                            : <div className={`grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] ${isMobile ? "gap-2.5" : "gap-4"}`}>
                                {filteredVideos.map(video => (
                                    <VideoGridCard key={video.id} video={video} isAdmin={isAdmin}
                                        onPlay={setPlayingVideo}
                                        onDelete={id => setVideos(prev => prev.filter(v => v.id !== id))}
                                        onUpdate={updated => setVideos(prev => prev.map(v => v.id === updated.id ? updated : v))} />
                                ))}
                            </div>
                    )}
                </div>
            </main>

            {showUpload && isAdmin && (
                <UploadModal
                    type={uploadType}
                    onClose={() => setShowUpload(false)}
                    onSuccess={() => { refreshBooks(); refreshVideos(); refreshAudio(); refreshBookTags(); }}
                />
            )}

            {editingBook && isAdmin && (
                <BookEditModal book={editingBook}
                    onClose={() => setEditingBook(null)}
                    onUpdate={updated => {
                        setBooks(prev => prev.map(b => b.uid === updated.uid ? updated : b));
                        setEditingBook(null);
                        refreshBookTags();
                    }} />
            )}

            {showAddAdmin && isAdmin && <AddAdminModal onClose={() => setShowAddAdmin(false)} />}

            {playingVideo && <VideoPlayerModal video={playingVideo} onClose={() => setPlayingVideo(null)} />}
        </div>
    );
};

export default Library;