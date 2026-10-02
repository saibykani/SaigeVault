"use client";

import type { FileSummary, FolderSummary } from "@saige/api-client";
import { formatBytes, formatRelativeTime } from "@saige/shared";
import { DOCUMENT_TYPE_LABELS } from "@saige/types";
import { useVirtualizer } from "@tanstack/react-virtual";
import {
  Download,
  Eye,
  FolderInput,
  Library,
  MoreHorizontal,
  Pencil,
  RotateCcw,
  Star,
  Tag,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { type MouseEvent, useRef } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { contentUrl } from "@/lib/files-api";
import { cn } from "@/lib/utils";
import type { FileViewMode } from "@/stores/ui-store";

import { FileIcon } from "./file-icon";

export interface FileListHandlers {
  onOpenFolder: (folder: FolderSummary) => void;
  onOpenFile: (file: FileSummary) => void;
  onSelect: (file: FileSummary, event: MouseEvent) => void;
  onRename: (file: FileSummary) => void;
  onMove: (file: FileSummary) => void;
  onTags: (file: FileSummary) => void;
  onCollection: (file: FileSummary) => void;
  onStar: (file: FileSummary) => void;
  onTrash: (file: FileSummary) => void;
  onRestore: (file: FileSummary) => void;
  onDeleteForever: (file: FileSummary) => void;
  onFolderRename: (folder: FolderSummary) => void;
  onFolderMove: (folder: FolderSummary) => void;
  onFolderDelete: (folder: FolderSummary) => void;
}

interface FileListProps extends FileListHandlers {
  folders: FolderSummary[];
  files: FileSummary[];
  selected: Set<string>;
  mode: FileViewMode;
  trashView: boolean;
}

const ROW_HEIGHT = 44;
const GRID =
  "grid grid-cols-[28px_minmax(0,1fr)_32px] items-center gap-3 md:grid-cols-[28px_minmax(0,3fr)_minmax(0,1.2fr)_88px_120px_32px]";

export function processingLabel(file: FileSummary): {
  text: string;
  variant: "outline" | "info" | "success" | "destructive";
} {
  switch (file.processing_status) {
    case "ready":
      return { text: "Ready", variant: "success" };
    case "failed":
      return { text: "Failed", variant: "destructive" };
    case "processing":
    case "queued":
      return { text: "Processing", variant: "info" };
    case "unsupported":
      return { text: "Stored", variant: "outline" };
    default:
      return { text: "Stored", variant: "outline" };
  }
}

function FileMenu({
  file,
  trashView,
  h,
}: {
  file: FileSummary;
  trashView: boolean;
  h: FileListHandlers;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label={`Actions for ${file.name}`}
          onClick={(e) => e.stopPropagation()}
        >
          <MoreHorizontal />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
        {trashView ? (
          <>
            <DropdownMenuItem onSelect={() => h.onRestore(file)}>
              <RotateCcw />
              Restore
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="text-destructive" onSelect={() => h.onDeleteForever(file)}>
              <Trash2 />
              Delete forever
            </DropdownMenuItem>
          </>
        ) : (
          <>
            <DropdownMenuItem asChild>
              <Link href={`/files/${file.id}`}>
                <Eye />
                Open
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <a href={contentUrl(file.id)} download>
                <Download />
                Download
              </a>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={() => h.onRename(file)}>
              <Pencil />
              Rename
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={() => h.onMove(file)}>
              <FolderInput />
              Move
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={() => h.onStar(file)}>
              <Star />
              {file.is_starred ? "Remove star" : "Star"}
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={() => h.onTags(file)}>
              <Tag />
              Tags
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={() => h.onCollection(file)}>
              <Library />
              Add to collection
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="text-destructive" onSelect={() => h.onTrash(file)}>
              <Trash2 />
              Move to trash
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function FolderMenu({ folder, h }: { folder: FolderSummary; h: FileListHandlers }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label={`Actions for folder ${folder.name}`}
          onClick={(e) => e.stopPropagation()}
        >
          <MoreHorizontal />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
        <DropdownMenuItem onSelect={() => h.onFolderRename(folder)}>
          <Pencil />
          Rename
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => h.onFolderMove(folder)}>
          <FolderInput />
          Move
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem className="text-destructive" onSelect={() => h.onFolderDelete(folder)}>
          <Trash2 />
          Delete
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

type Entry = { kind: "folder"; folder: FolderSummary } | { kind: "file"; file: FileSummary };

export function FileList(props: FileListProps) {
  const { folders, files, selected, mode, trashView } = props;
  const entries: Entry[] = [
    ...folders.map((folder) => ({ kind: "folder" as const, folder })),
    ...files.map((file) => ({ kind: "file" as const, file })),
  ];
  const scrollRef = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: entries.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 12,
  });

  if (mode === "grid") return <FileGrid {...props} entries={entries} />;

  return (
    <div
      role="grid"
      aria-label="Files"
      aria-multiselectable="true"
      className="flex min-h-0 flex-1 flex-col"
    >
      <div
        role="row"
        className={cn(GRID, "border-b px-4 py-2 text-xs font-medium text-muted-foreground sm:px-6")}
      >
        <span role="columnheader">
          <span className="sr-only">Select</span>
        </span>
        <span role="columnheader">Name</span>
        <span role="columnheader" className="hidden md:block">
          Type
        </span>
        <span role="columnheader" className="hidden text-right md:block">
          Size
        </span>
        <span role="columnheader" className="hidden md:block">
          {trashView ? "Deleted" : "Modified"}
        </span>
        <span role="columnheader">
          <span className="sr-only">Actions</span>
        </span>
      </div>
      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto">
        <div style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
          {virtualizer.getVirtualItems().map((row) => {
            const entry = entries[row.index]!;
            const style = {
              position: "absolute" as const,
              top: 0,
              left: 0,
              right: 0,
              height: ROW_HEIGHT,
              transform: `translateY(${row.start}px)`,
            };
            if (entry.kind === "folder") {
              const folder = entry.folder;
              return (
                <div
                  key={`d-${folder.id}`}
                  role="row"
                  style={style}
                  tabIndex={0}
                  onDoubleClick={() => props.onOpenFolder(folder)}
                  onKeyDown={(e) => e.key === "Enter" && props.onOpenFolder(folder)}
                  className={cn(
                    GRID,
                    "cursor-default border-b px-4 text-sm hover:bg-muted/60 sm:px-6",
                  )}
                >
                  <span />
                  <button
                    type="button"
                    className="flex min-w-0 items-center gap-2.5 text-left"
                    onClick={() => props.onOpenFolder(folder)}
                  >
                    <FileIcon folder />
                    <span className="truncate font-medium">{folder.name}</span>
                  </button>
                  <span className="hidden text-muted-foreground md:block">Folder</span>
                  <span className="hidden text-right text-muted-foreground md:block">—</span>
                  <span className="hidden text-muted-foreground md:block">
                    {formatRelativeTime(new Date(folder.updated_at))}
                  </span>
                  <FolderMenu folder={folder} h={props} />
                </div>
              );
            }
            const file = entry.file;
            const isSelected = selected.has(file.id);
            const status = processingLabel(file);
            return (
              <div
                key={file.id}
                role="row"
                aria-selected={isSelected}
                style={style}
                onClick={(e) => props.onSelect(file, e)}
                onDoubleClick={() => !trashView && props.onOpenFile(file)}
                className={cn(
                  GRID,
                  "cursor-default border-b px-4 text-sm select-none hover:bg-muted/60 sm:px-6",
                  isSelected && "bg-accent hover:bg-accent",
                )}
              >
                <input
                  type="checkbox"
                  aria-label={`Select ${file.name}`}
                  checked={isSelected}
                  onClick={(e) => e.stopPropagation()}
                  onChange={(e) => props.onSelect(file, e as unknown as MouseEvent)}
                  className="size-4 accent-primary"
                />
                <span className="flex min-w-0 items-center gap-2.5">
                  <FileIcon extension={file.extension} />
                  {trashView ? (
                    <span className="truncate">{file.name}</span>
                  ) : (
                    <Link
                      href={`/files/${file.id}`}
                      className="truncate hover:underline"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {file.name}
                    </Link>
                  )}
                  {file.is_starred ? (
                    <Star
                      className="size-3.5 shrink-0 fill-warning text-warning"
                      aria-label="Starred"
                    />
                  ) : null}
                  {file.tags?.slice(0, 2).map((t) => (
                    <Badge key={t.id} variant="outline" className="hidden lg:inline-flex">
                      #{t.name}
                    </Badge>
                  ))}
                </span>
                <span className="hidden min-w-0 items-center gap-1.5 md:flex">
                  <span className="truncate text-muted-foreground">
                    {DOCUMENT_TYPE_LABELS[file.document_type]}
                  </span>
                  <Badge variant={status.variant} className="hidden xl:inline-flex">
                    {status.text}
                  </Badge>
                </span>
                <span className="hidden text-right text-muted-foreground tabular-nums md:block">
                  {formatBytes(file.size_bytes)}
                </span>
                <span className="hidden truncate text-muted-foreground md:block">
                  {formatRelativeTime(
                    new Date(trashView && file.deleted_at ? file.deleted_at : file.updated_at),
                  )}
                </span>
                <FileMenu file={file} trashView={trashView} h={props} />
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function FileGrid(props: FileListProps & { entries: Entry[] }) {
  const { entries, selected, trashView } = props;
  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-6">
      <ul
        className="grid grid-cols-[repeat(auto-fill,minmax(10.5rem,1fr))] gap-3"
        aria-label="Files"
      >
        {entries.map((entry) =>
          entry.kind === "folder" ? (
            <li
              key={`d-${entry.folder.id}`}
              className="group relative rounded-lg border bg-card hover:bg-muted/50"
            >
              <button
                type="button"
                className="flex w-full items-center gap-2.5 p-3 text-left text-sm"
                onClick={() => props.onOpenFolder(entry.folder)}
              >
                <FileIcon folder className="size-5" />
                <span className="truncate font-medium">{entry.folder.name}</span>
              </button>
              <div className="absolute top-1.5 right-1.5 opacity-0 group-hover:opacity-100 focus-within:opacity-100">
                <FolderMenu folder={entry.folder} h={props} />
              </div>
            </li>
          ) : (
            <li
              key={entry.file.id}
              aria-label={`${entry.file.name}${selected.has(entry.file.id) ? ", selected" : ""}`}
              onClick={(e) => props.onSelect(entry.file, e)}
              className={cn(
                "group relative flex flex-col rounded-lg border bg-card transition-colors hover:bg-muted/50",
                selected.has(entry.file.id) && "border-primary/60 bg-accent",
              )}
            >
              <div className="flex aspect-[4/3] items-center justify-center overflow-hidden rounded-t-lg border-b bg-surface-muted">
                <FileIcon extension={entry.file.extension} className="size-9" />
              </div>
              <div className="flex items-center gap-1.5 p-2.5">
                {trashView ? (
                  <span className="min-w-0 flex-1 truncate text-[13px] font-medium">
                    {entry.file.name}
                  </span>
                ) : (
                  <Link
                    href={`/files/${entry.file.id}`}
                    onClick={(e) => e.stopPropagation()}
                    className="min-w-0 flex-1 truncate text-[13px] font-medium hover:underline"
                  >
                    {entry.file.name}
                  </Link>
                )}
                {entry.file.is_starred ? (
                  <Star
                    className="size-3.5 shrink-0 fill-warning text-warning"
                    aria-label="Starred"
                  />
                ) : null}
              </div>
              <p className="px-2.5 pb-2.5 text-xs text-muted-foreground">
                {formatBytes(entry.file.size_bytes)} ·{" "}
                {formatRelativeTime(new Date(entry.file.updated_at))}
              </p>
              <div className="absolute top-1.5 right-1.5 rounded-md bg-card/90 opacity-0 group-hover:opacity-100 focus-within:opacity-100">
                <FileMenu file={entry.file} trashView={trashView} h={props} />
              </div>
            </li>
          ),
        )}
      </ul>
    </div>
  );
}
