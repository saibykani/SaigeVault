"use client";

import type { FileSummary } from "@saige/api-client";
import { formatBytes, formatRelativeTime } from "@saige/shared";
import { DOCUMENT_TYPE_LABELS, DocumentType } from "@saige/types";
import {
  ArrowLeft,
  Download,
  Expand,
  FileQuestion,
  FolderInput,
  Library,
  Pencil,
  RotateCw,
  Star,
  Tag,
  Trash2,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/common/empty-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { contentUrl, errorMessage, useFile, useUpdateFile } from "@/lib/files-api";

import { FileIcon } from "./file-icon";
import { processingLabel } from "./file-list";
import { useFileActions } from "./use-file-actions";

const PdfViewer = dynamic(() => import("./pdf-viewer").then((m) => m.PdfViewer), {
  ssr: false,
  loading: () => <Skeleton className="m-6 h-[70vh]" />,
});

const IMAGE = new Set(["png", "jpg", "jpeg", "webp", "gif"]);
const TEXT = new Set(["txt", "md", "csv", "json", "xml"]);
const TEXT_PREVIEW_LIMIT = 512 * 1024;

function ImageViewer({ file }: { file: FileSummary }) {
  const [zoom, setZoom] = useState(1);
  const [rotation, setRotation] = useState(0);
  const frame = useRef<HTMLDivElement>(null);
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div
        className="flex items-center justify-center gap-1.5 border-b px-3 py-2"
        role="toolbar"
        aria-label="Image controls"
      >
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Zoom out"
          onClick={() => setZoom(Math.max(0.25, zoom / 1.25))}
        >
          <ZoomOut />
        </Button>
        <span className="w-12 text-center text-xs text-muted-foreground tabular-nums">
          {Math.round(zoom * 100)}%
        </span>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Zoom in"
          onClick={() => setZoom(Math.min(8, zoom * 1.25))}
        >
          <ZoomIn />
        </Button>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Rotate"
          onClick={() => setRotation((rotation + 90) % 360)}
        >
          <RotateCw />
        </Button>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Fullscreen"
          onClick={() => void frame.current?.requestFullscreen()}
        >
          <Expand />
        </Button>
      </div>
      <div
        ref={frame}
        className="flex min-h-0 flex-1 items-center justify-center overflow-auto bg-surface-muted p-4"
      >
        {/* eslint-disable-next-line @next/next/no-img-element -- authenticated same-origin content, not optimisable */}
        <img
          src={contentUrl(file.id, true)}
          alt={file.name}
          className="max-h-full max-w-full object-contain transition-transform"
          style={{ transform: `scale(${zoom}) rotate(${rotation}deg)` }}
        />
      </div>
    </div>
  );
}

function TextViewer({ file }: { file: FileSummary }) {
  const [text, setText] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let cancelled = false;
    fetch(contentUrl(file.id, true), { credentials: "include" })
      .then((r) => (r.ok ? r.text() : Promise.reject(new Error(String(r.status)))))
      .then((t) => !cancelled && setText(t.slice(0, TEXT_PREVIEW_LIMIT)))
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, [file.id]);
  if (failed)
    return (
      <p className="p-8 text-center text-sm text-muted-foreground">
        This file couldn&apos;t be displayed.
      </p>
    );
  if (text === null) return <Skeleton className="m-6 h-96" />;
  return (
    <div className="min-h-0 flex-1 overflow-auto bg-surface-muted p-4">
      {/* Rendered as text only — never interpreted as HTML or Markdown. */}
      <pre className="mx-auto max-w-4xl rounded-lg border bg-card p-5 font-mono text-[13px] leading-relaxed break-words whitespace-pre-wrap">
        {text}
        {file.size_bytes > TEXT_PREVIEW_LIMIT
          ? "\n\n… preview truncated. Download to see the whole file."
          : ""}
      </pre>
    </div>
  );
}

function Detail({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-3 py-2 text-sm">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 text-right font-medium">{children}</dd>
    </div>
  );
}

export function FilePreview({ id }: { id: string }) {
  const router = useRouter();
  const params = useSearchParams();
  const initialPage = Number(params.get("page")) || 1;
  const { data: file, isLoading, isError, error } = useFile(id);
  const update = useUpdateFile();
  const actions = useFileActions();

  if (isLoading) {
    return (
      <div className="p-6">
        <Skeleton className="h-10 w-80" />
        <Skeleton className="mt-6 h-[60vh]" />
      </div>
    );
  }
  if (isError || !file) {
    return (
      <EmptyState
        icon={FileQuestion}
        title="File not found"
        description={errorMessage(error, "It may have been deleted, or it isn't yours.")}
      >
        <Button size="sm" asChild>
          <Link href="/files">Back to files</Link>
        </Button>
      </EmptyState>
    );
  }

  const ext = file.extension ?? "";
  const trashed = Boolean(file.deleted_at);
  const status = processingLabel(file);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex flex-wrap items-center gap-2 border-b px-4 py-3 sm:px-6">
        <Button variant="ghost" size="icon-sm" aria-label="Back" onClick={() => router.back()}>
          <ArrowLeft />
        </Button>
        <FileIcon extension={file.extension} className="size-5" />
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-base font-semibold">{file.name}</h1>
          <p className="text-xs text-muted-foreground">
            {formatBytes(file.size_bytes)} · updated {formatRelativeTime(new Date(file.updated_at))}
            {trashed ? " · in trash" : ""}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <Button size="sm" variant="outline" asChild>
            <a href={contentUrl(file.id)} download>
              <Download />
              Download
            </a>
          </Button>
          {!trashed ? (
            <>
              <Button
                size="icon-sm"
                variant="ghost"
                aria-label={file.is_starred ? "Remove star" : "Star"}
                aria-pressed={file.is_starred}
                onClick={() => void actions.star([file.id], !file.is_starred)}
              >
                <Star className={file.is_starred ? "fill-warning text-warning" : undefined} />
              </Button>
              <Button
                size="icon-sm"
                variant="ghost"
                aria-label="Rename"
                onClick={() => actions.open({ type: "rename", file })}
              >
                <Pencil />
              </Button>
              <Button
                size="icon-sm"
                variant="ghost"
                aria-label="Move"
                onClick={() => actions.open({ type: "move", fileIds: [file.id] })}
              >
                <FolderInput />
              </Button>
              <Button
                size="icon-sm"
                variant="ghost"
                aria-label="Tags"
                onClick={() => actions.open({ type: "tags", file })}
              >
                <Tag />
              </Button>
              <Button
                size="icon-sm"
                variant="ghost"
                aria-label="Add to collection"
                onClick={() => actions.open({ type: "collection", fileIds: [file.id] })}
              >
                <Library />
              </Button>
              <Button
                size="icon-sm"
                variant="ghost"
                aria-label="Move to trash"
                onClick={async () => {
                  await actions.trash([file.id]);
                  router.push("/files");
                }}
              >
                <Trash2 />
              </Button>
            </>
          ) : null}
        </div>
      </header>

      <div className="grid min-h-0 flex-1 lg:grid-cols-[minmax(0,1fr)_300px]">
        <section aria-label="Preview" className="flex min-h-[50vh] flex-col border-r">
          {ext === "pdf" ? (
            <PdfViewer url={contentUrl(file.id, true)} initialPage={initialPage} />
          ) : IMAGE.has(ext) ? (
            <ImageViewer file={file} />
          ) : TEXT.has(ext) ? (
            <TextViewer file={file} />
          ) : (
            <EmptyState
              icon={FileQuestion}
              title="No preview for this file type"
              description="Download the file to open it. Text extraction for Office documents arrives with document processing (Phase 7)."
            >
              <Button size="sm" asChild>
                <a href={contentUrl(file.id)} download>
                  <Download />
                  Download
                </a>
              </Button>
            </EmptyState>
          )}
        </section>

        <aside aria-label="Details" className="overflow-y-auto p-4">
          <h2 className="text-sm font-semibold">Details</h2>
          <dl className="mt-2 divide-y">
            <Detail label="Document type">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button type="button" className="rounded px-1 hover:bg-muted" disabled={trashed}>
                    {DOCUMENT_TYPE_LABELS[file.document_type]}
                    {file.document_type_source === "user" ? (
                      <span className="ml-1 text-xs text-muted-foreground">(you)</span>
                    ) : file.document_type_source === "ai" ? (
                      <span className="ml-1 text-xs text-muted-foreground">(AI)</span>
                    ) : null}
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="max-h-80 overflow-y-auto">
                  <DropdownMenuRadioGroup
                    value={file.document_type}
                    onValueChange={(value) =>
                      update.mutate(
                        {
                          id: file.id,
                          patch: { document_type: value as FileSummary["document_type"] },
                        },
                        { onError: (e) => toast.error(errorMessage(e, "Couldn't update type")) },
                      )
                    }
                  >
                    {Object.values(DocumentType).map((t) => (
                      <DropdownMenuRadioItem key={t} value={t}>
                        {DOCUMENT_TYPE_LABELS[t]}
                      </DropdownMenuRadioItem>
                    ))}
                  </DropdownMenuRadioGroup>
                </DropdownMenuContent>
              </DropdownMenu>
            </Detail>
            <Detail label="Format">{ext.toUpperCase() || "—"}</Detail>
            <Detail label="Size">{formatBytes(file.size_bytes)}</Detail>
            <Detail label="Added">{new Date(file.created_at).toLocaleDateString()}</Detail>
            <Detail label="Modified">{new Date(file.updated_at).toLocaleString()}</Detail>
            <Detail label="Status">
              <Badge variant={status.variant}>{status.text}</Badge>
            </Detail>
          </dl>
          <h2 className="mt-5 text-sm font-semibold">Tags</h2>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {file.tags?.length ? (
              file.tags.map((t) => (
                <Link key={t.id} href={`/files?tag=${encodeURIComponent(t.name)}&view=all`}>
                  <Badge variant="outline">#{t.name}</Badge>
                </Link>
              ))
            ) : (
              <p className="text-xs text-muted-foreground">No tags yet.</p>
            )}
          </div>
          <p className="mt-6 rounded-md border border-dashed p-3 text-xs text-muted-foreground">
            Text extraction, OCR, AI summaries and structured data arrive with document processing
            (Phase 7). The original stays in your Google Drive.
          </p>
        </aside>
      </div>
      {actions.dialogs}
    </div>
  );
}
