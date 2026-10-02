import { create } from "zustand";

export type UploadStatus = "queued" | "uploading" | "done" | "error" | "cancelled";

export interface UploadItem {
  id: string;
  name: string;
  size: number;
  folderId?: string;
  progress: number;
  status: UploadStatus;
  error?: string;
  fileId?: string;
}

export const MAX_CONCURRENT_UPLOADS = 3;

interface UploadState {
  items: UploadItem[];
  /** Folder new uploads go to (set by the file explorer). */
  targetFolderId?: string;
  setTargetFolder: (folderId: string | undefined) => void;
  enqueue: (items: Omit<UploadItem, "progress" | "status">[]) => void;
  update: (id: string, patch: Partial<UploadItem>) => void;
  clearFinished: () => void;
}

/** In-memory only: file contents and names are never persisted in the browser. */
export const useUploadStore = create<UploadState>()((set) => ({
  items: [],
  targetFolderId: undefined,
  setTargetFolder: (targetFolderId) => set({ targetFolderId }),
  enqueue: (items) =>
    set((s) => ({
      items: [...s.items, ...items.map((i) => ({ ...i, progress: 0, status: "queued" as const }))],
    })),
  update: (id, patch) =>
    set((s) => ({ items: s.items.map((i) => (i.id === id ? { ...i, ...patch } : i)) })),
  clearFinished: () =>
    set((s) => ({
      items: s.items.filter((i) => i.status === "queued" || i.status === "uploading"),
    })),
}));

/** Which queued items may start now, respecting the concurrency limit. */
export function nextToStart(items: UploadItem[], limit = MAX_CONCURRENT_UPLOADS): UploadItem[] {
  const active = items.filter((i) => i.status === "uploading").length;
  return items.filter((i) => i.status === "queued").slice(0, Math.max(0, limit - active));
}
