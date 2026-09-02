import { useState, useEffect, useRef, useCallback, RefObject } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import type { PDFDocumentProxy, RenderTask } from 'pdfjs-dist';
import { getBookReadUrl } from '../services/api/books';

interface UsePdfViewerResult {
    loading: boolean;
    error: string | null;
    currentPage: number;
    totalPages: number;
    scale: number | null;
    rendering: boolean;
    goTo: (n: number) => void;
    zoom: (dir: 1 | -1) => void;
}

export function usePdfViewer(
    uid: string | undefined,
    containerRef: RefObject<HTMLDivElement | null>,
    canvasRef: RefObject<HTMLCanvasElement | null>,
): UsePdfViewerResult {
    const pdfRef = useRef<PDFDocumentProxy | null>(null);
    const renderTaskRef = useRef<RenderTask | null>(null);

    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    const [currentPage, setCurrentPage] = useState<number>(1);
    const [totalPages, setTotalPages] = useState<number>(0);
    const [scale, setScale] = useState<number | null>(null);
    const [rendering, setRendering] = useState<boolean>(false);

    // Portrait = fit to width (92%), Landscape/desktop = fit to height (92%)
    const computeFitScale = useCallback(async (pdf: PDFDocumentProxy, pageNum: number): Promise<number> => {
        if (!containerRef.current) return 1.2;
        const page = await pdf.getPage(pageNum);
        const baseViewport = page.getViewport({ scale: 1 });
        const isPortrait = window.innerHeight > window.innerWidth;

        if (isPortrait) {
            const containerWidth = containerRef.current.clientWidth * 0.92;
            return parseFloat((containerWidth / baseViewport.width).toFixed(2));
        } else {
            const availableHeight = containerRef.current.clientHeight * 0.92;
            return parseFloat((availableHeight / baseViewport.height).toFixed(2));
        }
    }, [containerRef]);

    // Load the document whenever `uid` changes
    useEffect(() => {
        let cancelled = false;

        const load = async () => {
            try {
                setLoading(true);
                setError(null);
                const pdf = await pdfjsLib.getDocument(getBookReadUrl(uid ?? '')).promise;
                if (cancelled) return;
                pdfRef.current = pdf;
                setTotalPages(pdf.numPages);
                setCurrentPage(1);
                const fitScale = await computeFitScale(pdf, 1);
                if (!cancelled) setScale(fitScale);
            } catch (e) {
                const err = e as { message?: string; name?: string };
                if (!cancelled) setError(`Failed to load book: ${err?.message || err?.name || 'Unknown error'}`);
            } finally {
                if (!cancelled) setLoading(false);
            }
        };

        load();
        return () => { cancelled = true; };
    }, [uid, computeFitScale]);

    // Recompute scale on resize / orientation change
    useEffect(() => {
        const handleResize = async () => {
            if (!pdfRef.current) return;
            const fitScale = await computeFitScale(pdfRef.current, currentPage);
            setScale(fitScale);
        };
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, [computeFitScale, currentPage]);

    // Render the current page whenever page/scale changes
    useEffect(() => {
        if (!pdfRef.current || loading || scale === null) return;

        const render = async () => {
            if (renderTaskRef.current) {
                renderTaskRef.current.cancel();
                renderTaskRef.current = null;
            }
            setRendering(true);
            try {
                const page = await pdfRef.current!.getPage(currentPage);
                const viewport = page.getViewport({ scale });
                const canvas = canvasRef.current;
                if (!canvas) return;
                canvas.width = viewport.width;
                canvas.height = viewport.height;
                const ctx = canvas.getContext('2d');
                if (!ctx) return;
                const task = page.render({ canvasContext: ctx, viewport });
                renderTaskRef.current = task;
                await task.promise;
            } catch (e) {
                const err = e as { name?: string; message?: string };
                if (err?.name !== 'RenderingCancelledException') {
                    setError(`Failed to render page: ${err?.message || err?.name || 'Unknown error'}`);
                }
            } finally {
                renderTaskRef.current = null;
                setRendering(false);
            }
        };

        render();
    }, [currentPage, scale, loading, canvasRef]);

    const goTo = useCallback((n: number) => {
        if (n < 1 || n > totalPages || rendering) return;
        setCurrentPage(n);
    }, [totalPages, rendering]);

    const zoom = useCallback((dir: 1 | -1) => {
        setScale(s => (s === null ? s : Math.min(3, Math.max(0.5, parseFloat((s + dir * 0.2).toFixed(1))))));
    }, []);

    return { loading, error, currentPage, totalPages, scale, rendering, goTo, zoom };
}