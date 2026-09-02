import { useState, ChangeEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useBooks } from "../hooks/useBooks";
import { BookUploader } from "../components/book/BookUploader";
import { BookCard } from "../components/book/BookCard";
import * as booksApi from "../api/books";
import { Book } from "../types";

type AlertType = "" | "success" | "error";

const UploadBook = () => {
    const { isAdmin } = useAuth();
    const navigate = useNavigate();
    const { books, refresh, setBooks } = useBooks();

    const [files, setFiles] = useState<File[]>([]);
    const [alert, setAlert] = useState<{ msg: string; type: AlertType }>({ msg: "", type: "" });
    const [loading, setLoading] = useState(false);
    const [deletingUid, setDeletingUid] = useState<Book['uid'] | null>(null);
    const [editingUid, setEditingUid] = useState<Book['uid'] | null>(null);
    const [editTitle, setEditTitle] = useState("");

    const handleFileSelect = (e: ChangeEvent<HTMLInputElement>) => {
        setFiles(Array.from(e.target.files ?? []));
        e.target.value = "";
    };

    const upload = async () => {
        if (files.length === 0) { setAlert({ msg: "// no file selected", type: "error" }); return; }
        setLoading(true);
        try {
            files.length === 1 ? await booksApi.uploadBook(files[0]) : await booksApi.uploadBooks(files);
            setAlert({ msg: `// ${files.length} book${files.length !== 1 ? "s" : ""} uploaded`, type: "success" });
            await refresh();
            setFiles([]);
        } catch {
            setAlert({ msg: "// upload failed — try again", type: "error" });
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async (uid: Book['uid']) => {
        setDeletingUid(uid);
        try {
            await booksApi.deleteBook(uid);
            setBooks(prev => prev.filter(b => b.uid !== uid));
        } catch {
            setAlert({ msg: "// delete failed", type: "error" });
        } finally {
            setDeletingUid(null);
        }
    };

    const saveEdit = async (uid: Book['uid']) => {
        try {
            const updated = await booksApi.updateBook(uid, editTitle);
            setBooks(prev => prev.map(b => b.uid === uid ? updated : b));
            setEditingUid(null);
        } catch {
            setAlert({ msg: "// update failed", type: "error" });
        }
    };

    if (!isAdmin) {
        return (
            <>
                {books.length === 0 ? (
                    <div className="text-center py-16 border border-dashed border-[#2a2a2a] rounded">
                        <p className="font-mono text-xs text-[#4a4540]">// no books in the archive yet</p>
                    </div>
                ) : (
                    <div className="grid grid-cols-[repeat(auto-fill,minmax(265px,1fr))] gap-5">
                        {books.map((book) => (
                            <BookCard
                                key={book.uid}
                                book={book}
                                isEditing={false}
                                isDeleting={false}
                                editTitle=""
                                onEditTitleChange={() => { }}
                                onStartEdit={() => { }}
                                onSaveEdit={() => { }}
                                onCancelEdit={() => { }}
                                onDelete={() => { }}
                                onRead={() => navigate(`/read/${book.uid}`)}
                            />
                        ))}
                    </div>
                )}
            </>
        );
    }

    return (
        <>
            <BookUploader
                files={files}
                loading={loading}
                alert={alert}
                onFileSelect={handleFileSelect}
                onRemoveFile={(i) => setFiles(prev => prev.filter((_, idx) => idx !== i))}
                onUpload={upload}
            />

            <div className="flex items-baseline gap-3 mb-4">
                <h2 className="font-serif text-xl font-semibold text-[#F0EAD6]">Library</h2>
                <span className="font-mono text-xs text-[#C9A84C]">{books.length} book{books.length !== 1 ? "s" : ""}</span>
            </div>
            <div className="relative h-px bg-[#2a2a2a] mb-6">
                <div className="absolute left-0 top-0 w-10 h-px bg-[#C9A84C]" />
            </div>

            {books.length === 0 ? (
                <div className="text-center py-16 border border-dashed border-[#2a2a2a] rounded">
                    <p className="font-mono text-xs text-[#4a4540]">// no books in the archive yet</p>
                </div>
            ) : (
                <div className="grid grid-cols-[repeat(auto-fill,minmax(265px,1fr))] gap-5">
                    {books.map((book) => (
                        <BookCard
                            key={book.uid}
                            book={book}
                            isEditing={editingUid === book.uid}
                            isDeleting={deletingUid === book.uid}
                            editTitle={editTitle}
                            onEditTitleChange={setEditTitle}
                            onStartEdit={() => { setEditingUid(book.uid); setEditTitle(book.title); }}
                            onSaveEdit={() => saveEdit(book.uid)}
                            onCancelEdit={() => setEditingUid(null)}
                            onDelete={() => handleDelete(book.uid)}
                            onRead={() => navigate(`/read/${book.uid}`)}
                        />
                    ))}
                </div>
            )}
        </>
    );
};

export default UploadBook;