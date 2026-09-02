import { useParams, useNavigate } from 'react-router-dom';
import { useRef } from 'react';
import { usePdfViewer } from '../hooks/usePdfViewer';
import { PdfToolbar } from '../components/books/PdfToolbar';
import { PdfCanvas } from '../components/books/PdfCanvas';
import { PdfPageControls } from '../components/books/PdfPageControls';

const ReadBook = () => {
    const { uid } = useParams<{ uid: string }>();
    const navigate = useNavigate();
    const canvasRef = useRef<HTMLCanvasElement | null>(null);
    const containerRef = useRef<HTMLDivElement | null>(null);

    const { loading, error, currentPage, totalPages, scale, rendering, goTo, zoom } =
        usePdfViewer(uid, containerRef, canvasRef);

    return (
        <div className="flex flex-col h-screen bg-[#1a1a1a] select-none">
            <PdfToolbar
                scale={scale}
                onBack={() => navigate(-1)}
                onZoomIn={() => zoom(1)}
                onZoomOut={() => zoom(-1)}
            />

            <PdfCanvas
                containerRef={containerRef}
                canvasRef={canvasRef}
                loading={loading}
                error={error}
                rendering={rendering}
                onSwipeNext={() => goTo(currentPage + 1)}
                onSwipePrev={() => goTo(currentPage - 1)}
            />

            <PdfPageControls
                currentPage={currentPage}
                totalPages={totalPages}
                rendering={rendering}
                onPrev={() => goTo(currentPage - 1)}
                onNext={() => goTo(currentPage + 1)}
            />
        </div>
    );
};

export default ReadBook;