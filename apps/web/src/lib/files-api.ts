"use client";

import {
  ApiError,
  type CollectionDetail,
  type CollectionSummary,
  CSRF_COOKIE,
  CSRF_HEADER,
  type FileListResponse,
  type FileStats,
  type FileSummary,
  type FolderSummary,
  type Schemas,
  readCookie,
  type TagRef,
} from "@saige/api-client";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";

export type SortKey = "name" | "updated" | "created" | "size" | "type";
export type TypeGroup =
  "pdf" | "image" | "document" | "spreadsheet" | "presentation" | "text" | "archive";

export interface FileQuery {
  folder_id?: string;
  q?: string;
  type?: TypeGroup;
  starred?: boolean;
  trashed?: boolean;
  tag?: string;
  collection_id?: string;
  all_folders?: boolean;
  sort?: SortKey;
  order?: "asc" | "desc";
  limit?: number;
}

export const fileKeys = {
  all: ["files"] as const,
  list: (q: FileQuery) => ["files", "list", q] as const,
  detail: (id: string) => ["files", "detail", id] as const,
  stats: ["files", "stats"] as const,
  tags: ["tags"] as const,
  collections: ["collections"] as const,
  collection: (id: string) => ["collections", id] as const,
};

function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.data !== undefined) return result.data;
  throw ApiError.fromResponse(result.response.status, result.error);
}

/** Error message suitable for a toast. */
export function errorMessage(error: unknown, fallback = "Something went wrong"): string {
  return error instanceof ApiError ? error.message : fallback;
}

// -- queries -------------------------------------------------------------------

export function useFiles(query: FileQuery, enabled = true) {
  return useQuery({
    queryKey: fileKeys.list(query),
    enabled,
    placeholderData: keepPreviousData,
    queryFn: async (): Promise<FileListResponse> =>
      unwrap(await api.GET("/api/v1/files", { params: { query } })),
  });
}

export function useFile(id: string) {
  return useQuery({
    queryKey: fileKeys.detail(id),
    queryFn: async (): Promise<FileSummary> =>
      unwrap(await api.GET("/api/v1/files/{file_id}", { params: { path: { file_id: id } } })),
  });
}

export function useFileStats(enabled = true) {
  return useQuery({
    queryKey: fileKeys.stats,
    enabled,
    queryFn: async (): Promise<FileStats> => unwrap(await api.GET("/api/v1/files/stats")),
  });
}

export function useTags() {
  return useQuery({
    queryKey: fileKeys.tags,
    queryFn: async (): Promise<TagRef[]> => unwrap(await api.GET("/api/v1/tags")).tags,
  });
}

export function useCollections(enabled = true) {
  return useQuery({
    queryKey: fileKeys.collections,
    enabled,
    queryFn: async (): Promise<CollectionSummary[]> =>
      unwrap(await api.GET("/api/v1/collections")).collections,
  });
}

export function useCollection(id: string) {
  return useQuery({
    queryKey: fileKeys.collection(id),
    queryFn: async (): Promise<CollectionDetail> =>
      unwrap(
        await api.GET("/api/v1/collections/{collection_id}", {
          params: { path: { collection_id: id } },
        }),
      ),
  });
}

// -- mutations -------------------------------------------------------------------

function useInvalidateVault() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: fileKeys.all }),
      queryClient.invalidateQueries({ queryKey: fileKeys.collections }),
      queryClient.invalidateQueries({ queryKey: fileKeys.tags }),
    ]);
}

export type FilePatch = Schemas["FileUpdate"];

export function useUpdateFile() {
  const invalidate = useInvalidateVault();
  return useMutation({
    mutationFn: async ({ id, patch }: { id: string; patch: FilePatch }) =>
      unwrap(
        await api.PATCH("/api/v1/files/{file_id}", {
          params: { path: { file_id: id } },
          body: patch,
        }),
      ),
    onSuccess: invalidate,
  });
}

export type BulkAction = "trash" | "restore" | "star" | "unstar" | "move";

export function useBulk() {
  const invalidate = useInvalidateVault();
  return useMutation({
    mutationFn: async (input: { file_ids: string[]; action: BulkAction; folder_id?: string }) =>
      unwrap(await api.POST("/api/v1/files/bulk", { body: input })),
    onSuccess: invalidate,
  });
}

export function useDeleteForever() {
  const invalidate = useInvalidateVault();
  return useMutation({
    mutationFn: async (id: string) => {
      const { error, response } = await api.DELETE("/api/v1/files/{file_id}/permanent", {
        params: { path: { file_id: id } },
      });
      if (!response.ok) throw ApiError.fromResponse(response.status, error);
    },
    onSuccess: invalidate,
  });
}

export function useSetTags() {
  const invalidate = useInvalidateVault();
  return useMutation({
    mutationFn: async ({ id, names }: { id: string; names: string[] }) =>
      unwrap(
        await api.PUT("/api/v1/files/{file_id}/tags", {
          params: { path: { file_id: id } },
          body: { names },
        }),
      ),
    onSuccess: invalidate,
  });
}

export function useCreateFolder() {
  const invalidate = useInvalidateVault();
  return useMutation({
    mutationFn: async (input: { name: string; parent_id?: string }): Promise<FolderSummary> =>
      unwrap(await api.POST("/api/v1/folders", { body: input })),
    onSuccess: invalidate,
  });
}

export function useUpdateFolder() {
  const invalidate = useInvalidateVault();
  return useMutation({
    mutationFn: async ({ id, patch }: { id: string; patch: Schemas["FolderUpdate"] }) =>
      unwrap(
        await api.PATCH("/api/v1/folders/{folder_id}", {
          params: { path: { folder_id: id } },
          body: patch,
        }),
      ),
    onSuccess: invalidate,
  });
}

export function useDeleteFolder() {
  const invalidate = useInvalidateVault();
  return useMutation({
    mutationFn: async (id: string) => {
      const { error, response } = await api.DELETE("/api/v1/folders/{folder_id}", {
        params: { path: { folder_id: id } },
      });
      if (!response.ok) throw ApiError.fromResponse(response.status, error);
    },
    onSuccess: invalidate,
  });
}

export function useCreateCollection() {
  const invalidate = useInvalidateVault();
  return useMutation({
    mutationFn: async (input: { name: string; description?: string }) =>
      unwrap(await api.POST("/api/v1/collections", { body: input })),
    onSuccess: invalidate,
  });
}

export function useAddToCollection() {
  const invalidate = useInvalidateVault();
  return useMutation({
    mutationFn: async ({ id, fileIds }: { id: string; fileIds: string[] }) =>
      unwrap(
        await api.POST("/api/v1/collections/{collection_id}/files", {
          params: { path: { collection_id: id } },
          body: { file_ids: fileIds },
        }),
      ),
    onSuccess: invalidate,
  });
}

export function useRemoveFromCollection() {
  const invalidate = useInvalidateVault();
  return useMutation({
    mutationFn: async ({ id, fileId }: { id: string; fileId: string }) => {
      const { error, response } = await api.DELETE(
        "/api/v1/collections/{collection_id}/files/{file_id}",
        { params: { path: { collection_id: id, file_id: fileId } } },
      );
      if (!response.ok) throw ApiError.fromResponse(response.status, error);
    },
    onSuccess: invalidate,
  });
}

export function useDeleteCollection() {
  const invalidate = useInvalidateVault();
  return useMutation({
    mutationFn: async (id: string) => {
      const { error, response } = await api.DELETE("/api/v1/collections/{collection_id}", {
        params: { path: { collection_id: id } },
      });
      if (!response.ok) throw ApiError.fromResponse(response.status, error);
    },
    onSuccess: invalidate,
  });
}

// -- content ---------------------------------------------------------------------

export function contentUrl(id: string, inline = false): string {
  return `/api/v1/files/${id}/content${inline ? "?inline=true" : ""}`;
}

// -- upload (XMLHttpRequest for progress events) ---------------------------------

export interface UploadOutcome {
  file?: FileSummary;
  error?: string;
}

function sendUpload(
  file: File,
  folderId: string | undefined,
  onProgress: (fraction: number) => void,
  signal?: AbortSignal,
): Promise<{ status: number; body: unknown }> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/v1/files");
    xhr.withCredentials = true;
    const csrf = readCookie(CSRF_COOKIE, document.cookie);
    if (csrf) xhr.setRequestHeader(CSRF_HEADER, csrf);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total);
    };
    xhr.onload = () => {
      let body: unknown = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        body = null;
      }
      resolve({ status: xhr.status, body });
    };
    xhr.onerror = () => reject(new Error("network"));
    xhr.onabort = () => reject(new DOMException("aborted", "AbortError"));
    signal?.addEventListener("abort", () => xhr.abort());
    const form = new FormData();
    form.append("file", file, file.name);
    if (folderId) form.append("folder_id", folderId);
    xhr.send(form);
  });
}

/** Uploads one file; refreshes the session once if it expired mid-way. */
export async function uploadFile(
  file: File,
  folderId: string | undefined,
  onProgress: (fraction: number) => void,
  signal?: AbortSignal,
): Promise<UploadOutcome> {
  try {
    let result = await sendUpload(file, folderId, onProgress, signal);
    if (result.status === 401) {
      const refreshed = await api.POST("/api/v1/auth/refresh", {});
      if (!refreshed.response.ok) return { error: "Your session expired. Sign in again." };
      result = await sendUpload(file, folderId, onProgress, signal);
    }
    if (result.status === 201) return { file: result.body as FileSummary };
    return { error: ApiError.fromResponse(result.status, result.body).message };
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") return { error: "Cancelled" };
    return { error: "Network error — check your connection and try again." };
  }
}
