"use client";

import { formatBytes } from "@saige/shared";
import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, ChevronDown, ChevronUp, Loader2, X, XCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { fileKeys, uploadFile } from "@/lib/files-api";
import { cn } from "@/lib/utils";
import { nextToStart, useUploadStore } from "@/stores/upload-store";

/** File objects live only in memory, keyed by upload id. */
const pendingFiles = new Map<string, File>();
const controllers = new Map<string, AbortController>();
let pickerInput: HTMLInputElement | null = null;

export const ACCEPTED_EXTENSIONS =
  ".pdf,.doc,.docx,.xls,.xlsx,.csv,.ppt,.pptx,.txt,.md,.json,.xml,.png,.jpg,.jpeg,.webp,.gif,.zip";

export function queueFiles(files: Iterable<File>, folderId?: string): number {
  const store = useUploadStore.getState();
  const target = folderId ?? store.targetFolderId;
  const items = Array.from(files).map((file) => {
    const id = crypto.randomUUID();
    pendingFiles.set(id, file);
    return { id, name: file.name, size: file.size, folderId: target };
  });
  store.enqueue(items);
  return items.length;
}

/** Opens the system file picker. Must be called from a user gesture. */
export function openFilePicker(): void {
  pickerInput?.click();
}

export function cancelUpload(id: string): void {
  controllers.get(id)?.abort();
  if (useUploadStore.getState().items.find((i) => i.id === id)?.status === "queued") {
    pendingFiles.delete(id);
    useUploadStore.getState().update(id, { status: "cancelled", error: "Cancelled" });
  }
}

export function UploadManager() {
  const items = useUploadStore((s) => s.items);
  const update = useUploadStore((s) => s.update);
  const clearFinished = useUploadStore((s) => s.clearFinished);
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    pickerInput = inputRef.current;
    return () => {
      pickerInput = null;
    };
  }, []);

  useEffect(() => {
    for (const item of nextToStart(items)) {
      const file = pendingFiles.get(item.id);
      if (!file) {
        update(item.id, { status: "error", error: "File is no longer available" });
        continue;
      }
      const controller = new AbortController();
      controllers.set(item.id, controller);
      update(item.id, { status: "uploading" });
      void uploadFile(
        file,
        item.folderId,
        (progress) => update(item.id, { progress }),
        controller.signal,
      ).then((outcome) => {
        pendingFiles.delete(item.id);
        controllers.delete(item.id);
        if (outcome.file) {
          update(item.id, { status: "done", progress: 1, fileId: outcome.file.id });
          void queryClient.invalidateQueries({ queryKey: fileKeys.all });
        } else {
          const cancelled = outcome.error === "Cancelled";
          update(item.id, { status: cancelled ? "cancelled" : "error", error: outcome.error });
        }
      });
    }
  }, [items, update, queryClient]);

  const active = items.filter((i) => i.status === "queued" || i.status === "uploading").length;
  const failed = items.filter((i) => i.status === "error").length;

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ACCEPTED_EXTENSIONS}
        className="hidden"
        aria-hidden="true"
        tabIndex={-1}
        onChange={(event) => {
          if (event.target.files?.length) queueFiles(event.target.files);
          event.target.value = "";
        }}
      />
      {items.length > 0 ? (
        <section
          aria-label="Uploads"
          className="fixed right-4 bottom-20 z-40 w-[min(22rem,calc(100vw-2rem))] overflow-hidden rounded-xl border bg-popover shadow-xl md:bottom-4"
        >
          <header className="flex items-center gap-2 border-b px-3 py-2">
            <p className="flex-1 text-sm font-medium" aria-live="polite">
              {active
                ? `Uploading ${active} file${active === 1 ? "" : "s"}…`
                : failed
                  ? `${failed} upload${failed === 1 ? "" : "s"} failed`
                  : "Uploads complete"}
            </p>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={collapsed ? "Expand uploads" : "Collapse uploads"}
              onClick={() => setCollapsed(!collapsed)}
            >
              {collapsed ? <ChevronUp /> : <ChevronDown />}
            </Button>
            {active === 0 ? (
              <Button variant="ghost" size="icon-sm" aria-label="Close" onClick={clearFinished}>
                <X />
              </Button>
            ) : null}
          </header>
          {collapsed ? null : (
            <ul className="max-h-72 divide-y overflow-y-auto">
              {items.map((item) => (
                <li key={item.id} className="px-3 py-2">
                  <div className="flex items-center gap-2 text-sm">
                    {item.status === "done" ? (
                      <CheckCircle2
                        className="size-4 shrink-0 text-success"
                        aria-label="Uploaded"
                      />
                    ) : item.status === "error" || item.status === "cancelled" ? (
                      <XCircle className="size-4 shrink-0 text-destructive" aria-label="Failed" />
                    ) : (
                      <Loader2 className="size-4 shrink-0 animate-spin text-muted-foreground" />
                    )}
                    <span className="min-w-0 flex-1 truncate">{item.name}</span>
                    <span className="shrink-0 text-xs text-muted-foreground tabular-nums">
                      {formatBytes(item.size)}
                    </span>
                    {item.status === "queued" || item.status === "uploading" ? (
                      <button
                        type="button"
                        onClick={() => cancelUpload(item.id)}
                        className="rounded p-0.5 text-muted-foreground hover:text-foreground"
                        aria-label={`Cancel ${item.name}`}
                      >
                        <X className="size-3.5" />
                      </button>
                    ) : null}
                  </div>
                  {item.status === "uploading" || item.status === "queued" ? (
                    <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-muted">
                      <div
                        className={cn(
                          "h-full bg-primary transition-[width]",
                          item.status === "queued" && "opacity-40",
                        )}
                        style={{ width: `${Math.round(item.progress * 100)}%` }}
                      />
                    </div>
                  ) : null}
                  {item.error && item.status !== "cancelled" ? (
                    <p className="mt-1 text-xs text-destructive">{item.error}</p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : null}
    </>
  );
}
