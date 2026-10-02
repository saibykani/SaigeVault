"use client";

import { ChevronLeft, ChevronRight, Loader2, Maximize2, ZoomIn, ZoomOut } from "lucide-react";
import type { PDFDocumentLoadingTask, PDFDocumentProxy, RenderTask } from "pdfjs-dist";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const MIN_ZOOM = 0.25;
const MAX_ZOOM = 4;

async function loadPdfJs() {
  const pdfjs = await import("pdfjs-dist");
  pdfjs.GlobalWorkerOptions.workerSrc = new URL(
    "pdfjs-dist/build/pdf.worker.min.mjs",
    import.meta.url,
  ).toString();
  return pdfjs;
}

/**
 * Renders a PDF to canvas with pdf.js. The document is fetched as bytes from
 * the same-origin content endpoint; no third-party viewer or iframe is used.
 */
export function PdfViewer({ url, initialPage = 1 }: { url: string; initialPage?: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [doc, setDoc] = useState<PDFDocumentProxy | null>(null);
  const [page, setPage] = useState(initialPage);
  const [zoom, setZoom] = useState<number | "fit">("fit");
  const [error, setError] = useState<string | null>(null);
  const [rendering, setRendering] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let task: PDFDocumentLoadingTask | null = null;
    (async () => {
      try {
        const [pdfjs, response] = await Promise.all([
          loadPdfJs(),
          fetch(url, { credentials: "include" }),
        ]);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = new Uint8Array(await response.arrayBuffer());
        task = pdfjs.getDocument({ data });
        const loaded = await task.promise;
        if (cancelled) return;
        setDoc(loaded);
        setPage((p) => Math.min(Math.max(1, p), loaded.numPages));
      } catch {
        if (!cancelled) setError("This PDF couldn't be displayed. You can still download it.");
      }
    })();
    return () => {
      cancelled = true;
      void task?.destroy();
    };
  }, [url]);

  useEffect(() => {
    if (!doc || !canvasRef.current) return;
    let task: RenderTask | null = null;
    let cancelled = false;
    (async () => {
      setRendering(true);
      const pdfPage = await doc.getPage(page);
      if (cancelled) return;
      const base = pdfPage.getViewport({ scale: 1 });
      const width = containerRef.current?.clientWidth ?? base.width;
      const scale = zoom === "fit" ? Math.max(MIN_ZOOM, (width - 32) / base.width) : zoom;
      const ratio = window.devicePixelRatio || 1;
      const viewport = pdfPage.getViewport({ scale: scale * ratio });
      const canvas = canvasRef.current!;
      canvas.width = Math.floor(viewport.width);
      canvas.height = Math.floor(viewport.height);
      canvas.style.width = `${Math.floor(viewport.width / ratio)}px`;
      canvas.style.height = `${Math.floor(viewport.height / ratio)}px`;
      task = pdfPage.render({ canvas, viewport });
      try {
        await task.promise;
      } catch {
        // cancelled by a newer render
      } finally {
        if (!cancelled) setRendering(false);
      }
    })();
    return () => {
      cancelled = true;
      task?.cancel();
    };
  }, [doc, page, zoom]);

  const pages = doc?.numPages ?? 0;
  const currentZoom = zoom === "fit" ? null : zoom;

  if (error) {
    return <p className="p-8 text-center text-sm text-muted-foreground">{error}</p>;
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div
        className="flex flex-wrap items-center justify-center gap-1.5 border-b px-3 py-2"
        role="toolbar"
        aria-label="PDF controls"
      >
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Previous page"
          disabled={page <= 1}
          onClick={() => setPage(page - 1)}
        >
          <ChevronLeft />
        </Button>
        <label className="flex items-center gap-1.5 text-sm">
          <span className="sr-only">Page</span>
          <Input
            className="h-7 w-14 text-center text-[13px]"
            inputMode="numeric"
            value={page}
            onChange={(e) => {
              const n = Number(e.target.value);
              if (Number.isInteger(n) && n >= 1 && n <= pages) setPage(n);
            }}
          />
          <span className="text-muted-foreground">of {pages || "…"}</span>
        </label>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Next page"
          disabled={page >= pages}
          onClick={() => setPage(page + 1)}
        >
          <ChevronRight />
        </Button>
        <span className="mx-2 h-5 w-px bg-border" aria-hidden="true" />
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Zoom out"
          onClick={() => setZoom(Math.max(MIN_ZOOM, (currentZoom ?? 1) / 1.25))}
        >
          <ZoomOut />
        </Button>
        <span className="w-12 text-center text-xs text-muted-foreground tabular-nums">
          {currentZoom ? `${Math.round(currentZoom * 100)}%` : "Fit"}
        </span>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Zoom in"
          onClick={() => setZoom(Math.min(MAX_ZOOM, (currentZoom ?? 1) * 1.25))}
        >
          <ZoomIn />
        </Button>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Fit to width"
          onClick={() => setZoom("fit")}
        >
          <Maximize2 />
        </Button>
        {rendering || !doc ? (
          <Loader2
            className="ml-1 size-4 animate-spin text-muted-foreground"
            aria-label="Loading"
          />
        ) : null}
      </div>
      <div ref={containerRef} className="min-h-0 flex-1 overflow-auto bg-surface-muted p-4">
        <canvas
          ref={canvasRef}
          className="mx-auto block bg-white shadow-md"
          aria-label={`Page ${page} of ${pages}`}
        />
      </div>
    </div>
  );
}
