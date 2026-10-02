"use client";

import type { FileSummary, FolderSummary } from "@saige/api-client";
import {
  ArrowDownUp,
  ChevronRight,
  FolderInput,
  FolderPlus,
  HardDrive,
  LayoutGrid,
  Library,
  List,
  ListFilter,
  RotateCcw,
  Search,
  Star,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  type DragEvent,
  type MouseEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/common/empty-state";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { Skeleton } from "@/components/ui/skeleton";
import { isTypingTarget } from "@/hooks/use-keyboard-shortcuts";
import { useSession, useStorageConnections } from "@/lib/api";
import {
  errorMessage,
  type FileQuery,
  type SortKey,
  type TypeGroup,
  useCreateFolder,
  useFiles,
} from "@/lib/files-api";
import { cn } from "@/lib/utils";
import { useUploadStore } from "@/stores/upload-store";
import { type FileViewMode, useUIStore } from "@/stores/ui-store";

import { NameDialog } from "./dialogs";
import { FileList } from "./file-list";
import { openFilePicker, queueFiles } from "./upload-manager";
import { useFileActions } from "./use-file-actions";

const SORTS: { value: SortKey; label: string }[] = [
  { value: "updated", label: "Last modified" },
  { value: "name", label: "Name" },
  { value: "size", label: "Size" },
  { value: "type", label: "Type" },
  { value: "created", label: "Date added" },
];

const TYPES: { value: TypeGroup | "all"; label: string }[] = [
  { value: "all", label: "All types" },
  { value: "pdf", label: "PDFs" },
  { value: "image", label: "Images" },
  { value: "document", label: "Documents" },
  { value: "spreadsheet", label: "Spreadsheets" },
  { value: "presentation", label: "Presentations" },
  { value: "text", label: "Text" },
  { value: "archive", label: "Archives" },
];

type View = "all" | "starred" | "trash";

export function FileExplorer() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const view = (params.get("view") as View | null) ?? "all";
  const folderId = params.get("folder") ?? undefined;
  const type = (params.get("type") as TypeGroup | null) ?? undefined;
  const sort = (params.get("sort") as SortKey | null) ?? "updated";
  const order =
    (params.get("order") as "asc" | "desc" | null) ?? (sort === "name" ? "asc" : "desc");
  const q = params.get("q") ?? "";

  const viewMode = useUIStore((s) => s.fileViewMode);
  const setViewMode = useUIStore((s) => s.setFileViewMode);
  const setTargetFolder = useUploadStore((s) => s.setTargetFolder);
  const [search, setSearch] = useState(q);
  // Selection belongs to one listing; changing folder/view/filters clears it.
  const listingKey = `${view}|${folderId ?? ""}|${q}|${type ?? ""}`;
  const [selection, setSelection] = useState<{ key: string; ids: Set<string> }>({
    key: listingKey,
    ids: new Set(),
  });
  const selected = useMemo(
    () => (selection.key === listingKey ? selection.ids : new Set<string>()),
    [selection, listingKey],
  );
  const setSelected = useCallback(
    (next: Set<string> | ((current: Set<string>) => Set<string>)) =>
      setSelection((prev) => {
        const current = prev.key === listingKey ? prev.ids : new Set<string>();
        return { key: listingKey, ids: typeof next === "function" ? next(current) : next };
      }),
    [listingKey],
  );
  const [anchor, setAnchor] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [newFolder, setNewFolder] = useState(false);
  const dragDepth = useRef(0);

  const { data: session } = useSession();
  const { data: connections } = useStorageConnections(Boolean(session));
  const driveReady = connections?.some((c) => c.status === "active") ?? false;

  const query: FileQuery = useMemo(
    () => ({
      folder_id: view === "all" ? folderId : undefined,
      q: q || undefined,
      type,
      starred: view === "starred" ? true : undefined,
      trashed: view === "trash" ? true : undefined,
      sort,
      order,
      limit: 500,
    }),
    [view, folderId, q, type, sort, order],
  );
  const { data, isLoading, isError, error, isFetching } = useFiles(query, Boolean(session));
  const files = useMemo(() => data?.files ?? [], [data]);
  const folders = data?.folders ?? [];
  const actions = useFileActions({ onDone: () => setSelected(new Set()) });
  const createFolder = useCreateFolder();

  const setParam = useCallback(
    (patch: Record<string, string | undefined>) => {
      const next = new URLSearchParams(params.toString());
      for (const [k, v] of Object.entries(patch)) {
        if (v === undefined || v === "") next.delete(k);
        else next.set(k, v);
      }
      const qs = next.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [params, pathname, router],
  );

  // Debounced search → URL.
  useEffect(() => {
    const handle = setTimeout(() => {
      if (search !== q) setParam({ q: search || undefined });
    }, 250);
    return () => clearTimeout(handle);
  }, [search, q, setParam]);

  useEffect(() => {
    setTargetFolder(view === "all" ? folderId : undefined);
    return () => setTargetFolder(undefined);
  }, [folderId, view, setTargetFolder]);

  const selectedFiles = files.filter((f) => selected.has(f.id));

  function onSelect(file: FileSummary, event: MouseEvent) {
    setSelected((current) => {
      const next = new Set(
        event.metaKey || event.ctrlKey || event.target instanceof HTMLInputElement ? current : [],
      );
      if (event.shiftKey && anchor) {
        const a = files.findIndex((f) => f.id === anchor);
        const b = files.findIndex((f) => f.id === file.id);
        for (const f of files.slice(Math.min(a, b), Math.max(a, b) + 1)) next.add(f.id);
      } else if (
        next.has(file.id) &&
        (event.metaKey || event.ctrlKey || event.target instanceof HTMLInputElement)
      ) {
        next.delete(file.id);
      } else {
        next.add(file.id);
      }
      return next;
    });
    if (!event.shiftKey) setAnchor(file.id);
  }

  // Keyboard shortcuts scoped to the explorer.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (isTypingTarget(event.target) || document.querySelector("[role=dialog]")) return;
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "a") {
        event.preventDefault();
        setSelected(new Set(files.map((f) => f.id)));
      } else if (event.key === "Escape") {
        setSelected(new Set());
      } else if (
        (event.key === "Delete" || event.key === "Backspace") &&
        selected.size &&
        view !== "trash"
      ) {
        event.preventDefault();
        void actions.trash([...selected]);
      } else if (event.key === "F2" && selectedFiles.length === 1) {
        event.preventDefault();
        actions.open({ type: "rename", file: selectedFiles[0]! });
      } else if (event.key === "Enter" && selectedFiles.length === 1 && view !== "trash") {
        router.push(`/files/${selectedFiles[0]!.id}`);
      } else if (
        event.key.toLowerCase() === "u" &&
        !event.ctrlKey &&
        !event.metaKey &&
        driveReady &&
        view !== "trash"
      ) {
        openFilePicker();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [files, selected, selectedFiles, view, actions, router, driveReady, setSelected]);

  function onDrop(event: DragEvent) {
    event.preventDefault();
    dragDepth.current = 0;
    setDragging(false);
    if (!driveReady || view === "trash") {
      toast.error("Connect Google Drive in Settings before uploading.");
      return;
    }
    const count = queueFiles(event.dataTransfer.files, folderId);
    if (count) toast.message(`Uploading ${count} file${count === 1 ? "" : "s"}…`);
  }

  const handlers = {
    onOpenFolder: (f: FolderSummary) => setParam({ folder: f.id, view: undefined, q: undefined }),
    onOpenFile: (f: FileSummary) => router.push(`/files/${f.id}`),
    onSelect,
    onRename: (file: FileSummary) => actions.open({ type: "rename", file }),
    onMove: (file: FileSummary) => actions.open({ type: "move", fileIds: [file.id] }),
    onTags: (file: FileSummary) => actions.open({ type: "tags", file }),
    onCollection: (file: FileSummary) => actions.open({ type: "collection", fileIds: [file.id] }),
    onStar: (file: FileSummary) => void actions.star([file.id], !file.is_starred),
    onTrash: (file: FileSummary) => void actions.trash([file.id]),
    onRestore: (file: FileSummary) => void actions.restore([file.id]),
    onDeleteForever: (file: FileSummary) => actions.open({ type: "deleteForever", files: [file] }),
    onFolderRename: (folder: FolderSummary) => actions.open({ type: "renameFolder", folder }),
    onFolderMove: (folder: FolderSummary) => actions.open({ type: "moveFolder", folder }),
    onFolderDelete: (folder: FolderSummary) => actions.open({ type: "deleteFolder", folder }),
  };

  const crumbs = data?.breadcrumbs ?? [{ id: null, name: "My Vault" }];
  const filtering = Boolean(q || type || view !== "all");
  const empty = !isLoading && !isError && folders.length === 0 && files.length === 0;

  return (
    <div
      className="relative flex min-h-0 flex-1 flex-col"
      onDragEnter={(e) => {
        if (!e.dataTransfer.types.includes("Files")) return;
        dragDepth.current += 1;
        setDragging(true);
      }}
      onDragLeave={() => {
        dragDepth.current = Math.max(0, dragDepth.current - 1);
        if (dragDepth.current === 0) setDragging(false);
      }}
      onDragOver={(e) => e.preventDefault()}
      onDrop={onDrop}
    >
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2 border-b px-4 py-3 sm:px-6">
        <SegmentedControl<View>
          ariaLabel="File views"
          value={view}
          onValueChange={(v) => setParam({ view: v === "all" ? undefined : v, folder: undefined })}
          options={[
            { value: "all", label: "All files", icon: HardDrive },
            { value: "starred", label: "Starred", icon: Star },
            { value: "trash", label: "Trash", icon: Trash2 },
          ]}
        />
        <div className="relative min-w-40 flex-1 sm:max-w-64">
          <Search
            className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter by name…"
            aria-label="Filter files by name"
            className="h-8 pl-8 text-[13px]"
          />
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" aria-label="Filter by type">
                <ListFilter />
                {TYPES.find((t) => t.value === (type ?? "all"))?.label}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>File type</DropdownMenuLabel>
              <DropdownMenuRadioGroup
                value={type ?? "all"}
                onValueChange={(v) => setParam({ type: v === "all" ? undefined : v })}
              >
                {TYPES.map((t) => (
                  <DropdownMenuRadioItem key={t.value} value={t.value}>
                    {t.label}
                  </DropdownMenuRadioItem>
                ))}
              </DropdownMenuRadioGroup>
            </DropdownMenuContent>
          </DropdownMenu>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" aria-label="Sort files">
                <ArrowDownUp />
                {SORTS.find((s) => s.value === sort)?.label}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Sort by</DropdownMenuLabel>
              <DropdownMenuRadioGroup
                value={sort}
                onValueChange={(v) => setParam({ sort: v, order: undefined })}
              >
                {SORTS.map((s) => (
                  <DropdownMenuRadioItem key={s.value} value={s.value}>
                    {s.label}
                  </DropdownMenuRadioItem>
                ))}
              </DropdownMenuRadioGroup>
              <DropdownMenuSeparator />
              <DropdownMenuRadioGroup value={order} onValueChange={(v) => setParam({ order: v })}>
                <DropdownMenuRadioItem value="asc">Ascending</DropdownMenuRadioItem>
                <DropdownMenuRadioItem value="desc">Descending</DropdownMenuRadioItem>
              </DropdownMenuRadioGroup>
            </DropdownMenuContent>
          </DropdownMenu>
          <SegmentedControl<FileViewMode>
            ariaLabel="View mode"
            value={viewMode}
            onValueChange={setViewMode}
            options={[
              { value: "list", label: "List view", icon: List, iconOnly: true },
              { value: "grid", label: "Grid view", icon: LayoutGrid, iconOnly: true },
            ]}
          />
          {view !== "trash" ? (
            <>
              <Button
                variant="outline"
                size="sm"
                disabled={!driveReady}
                onClick={() => setNewFolder(true)}
              >
                <FolderPlus />
                New folder
              </Button>
              <Button size="sm" disabled={!driveReady} onClick={openFilePicker}>
                <Upload />
                Upload
              </Button>
            </>
          ) : null}
        </div>
      </div>

      {/* Breadcrumbs / selection bar */}
      {selected.size ? (
        <div
          className="flex flex-wrap items-center gap-2 border-b bg-accent/60 px-4 py-2 text-sm sm:px-6"
          role="toolbar"
          aria-label="Selection actions"
        >
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="Clear selection"
            onClick={() => setSelected(new Set())}
          >
            <X />
          </Button>
          <span className="mr-2 font-medium">{selected.size} selected</span>
          {view === "trash" ? (
            <>
              <Button
                size="sm"
                variant="outline"
                onClick={() => void actions.restore([...selected])}
              >
                <RotateCcw />
                Restore
              </Button>
              <Button
                size="sm"
                variant="destructive"
                onClick={() => actions.open({ type: "deleteForever", files: selectedFiles })}
              >
                <Trash2 />
                Delete forever
              </Button>
            </>
          ) : (
            <>
              <Button
                size="sm"
                variant="outline"
                onClick={() => void actions.star([...selected], true)}
              >
                <Star />
                Star
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => actions.open({ type: "move", fileIds: [...selected] })}
              >
                <FolderInput />
                Move
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => actions.open({ type: "collection", fileIds: [...selected] })}
              >
                <Library />
                Add to collection
              </Button>
              <Button size="sm" variant="outline" onClick={() => void actions.trash([...selected])}>
                <Trash2 />
                Trash
              </Button>
            </>
          )}
        </div>
      ) : (
        <nav
          aria-label="Breadcrumb"
          className="flex min-h-10 flex-wrap items-center gap-1 border-b px-4 py-2 text-sm sm:px-6"
        >
          {view === "all" ? (
            crumbs.map((c, i) => (
              <span key={c.id ?? "root"} className="flex items-center gap-1">
                {i > 0 ? (
                  <ChevronRight className="size-3.5 text-muted-foreground" aria-hidden="true" />
                ) : (
                  <HardDrive className="mr-1 size-4 text-muted-foreground" aria-hidden="true" />
                )}
                {i === crumbs.length - 1 ? (
                  <span className="font-medium" aria-current="page">
                    {c.name}
                  </span>
                ) : (
                  <button
                    type="button"
                    className="rounded px-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                    onClick={() => setParam({ folder: c.id ?? undefined })}
                  >
                    {c.name}
                  </button>
                )}
              </span>
            ))
          ) : (
            <span className="font-medium">{view === "trash" ? "Trash" : "Starred"}</span>
          )}
          <span className="ml-auto text-xs text-muted-foreground" aria-live="polite">
            {isFetching && !isLoading
              ? "Updating…"
              : data
                ? `${data.total} file${data.total === 1 ? "" : "s"}`
                : ""}
          </span>
        </nav>
      )}

      {session && connections && !driveReady && view !== "trash" ? (
        <div
          role="note"
          className="mx-4 mt-4 flex flex-wrap items-center gap-3 rounded-lg border border-warning/30 bg-warning/5 px-4 py-3 text-sm sm:mx-6"
        >
          <HardDrive className="size-4 text-warning" aria-hidden="true" />
          <span className="flex-1 text-muted-foreground">
            Connect Google Drive to upload. Your files are stored in your own Drive.
          </span>
          <Button size="sm" asChild>
            <Link href="/settings#storage">Connect Drive</Link>
          </Button>
        </div>
      ) : null}

      {/* Content */}
      {isLoading ? (
        <div className="space-y-2 p-6">
          {Array.from({ length: 8 }, (_, i) => (
            <Skeleton key={i} className="h-9" />
          ))}
        </div>
      ) : isError ? (
        <EmptyState
          icon={X}
          title="Couldn't load files"
          description={errorMessage(error, "The server didn't respond.")}
        />
      ) : empty ? (
        <div className="p-4 sm:p-6">
          <div
            className={cn(
              "rounded-xl border-2 border-dashed",
              dragging ? "border-primary bg-accent/50" : "border-border",
            )}
          >
            {view === "trash" ? (
              <EmptyState
                icon={Trash2}
                title="Trash is empty"
                description="Files you delete stay here until you delete them forever."
              />
            ) : view === "starred" ? (
              <EmptyState
                icon={Star}
                title="No starred files"
                description="Star important documents for one-tap access."
              />
            ) : filtering ? (
              <EmptyState
                icon={Search}
                title="No matching files"
                description="Try a different name or filter."
              />
            ) : (
              <EmptyState
                icon={Upload}
                title={folderId ? "This folder is empty" : "Your vault is empty"}
                description="Drag files here or use Upload. PDFs, Office documents, images, text and ZIP archives are supported (up to 100 MB)."
              >
                <Button size="sm" disabled={!driveReady} onClick={openFilePicker}>
                  <Upload />
                  Upload files
                </Button>
              </EmptyState>
            )}
          </div>
        </div>
      ) : (
        <FileList
          folders={folders}
          files={files}
          selected={selected}
          mode={viewMode}
          trashView={view === "trash"}
          {...handlers}
        />
      )}

      {dragging && driveReady && view !== "trash" ? (
        <div className="pointer-events-none absolute inset-2 z-20 flex items-center justify-center rounded-xl border-2 border-dashed border-primary bg-background/80 backdrop-blur-sm">
          <p className="flex items-center gap-2 text-sm font-medium">
            <Upload className="size-4 text-primary" aria-hidden="true" />
            Drop to upload to {crumbs.at(-1)?.name ?? "My Vault"}
          </p>
        </div>
      ) : null}

      {newFolder ? (
        <NameDialog
          open
          onOpenChange={setNewFolder}
          title="New folder"
          label="Folder name"
          submitLabel="Create"
          pending={createFolder.isPending}
          onSubmit={(name) =>
            createFolder.mutate(
              { name, ...(folderId ? { parent_id: folderId } : {}) },
              {
                onSuccess: () => setNewFolder(false),
                onError: (e) => toast.error(errorMessage(e, "Couldn't create folder")),
              },
            )
          }
        />
      ) : null}
      {actions.dialogs}
    </div>
  );
}
