"use client";

import { DOCUMENT_TYPE_LABELS } from "@saige/types";
import {
  ArrowDownUp,
  ChevronRight,
  FolderPlus,
  HardDrive,
  LayoutGrid,
  List,
  ListFilter,
  Upload,
} from "lucide-react";
import { type DragEvent, useState } from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/common/empty-state";
import { FeatureNotice } from "@/components/common/feature-notice";
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
import { SegmentedControl } from "@/components/ui/segmented-control";
import { feature } from "@/lib/features";
import { cn } from "@/lib/utils";
import { type FileViewMode, useUIStore } from "@/stores/ui-store";

const SORT_OPTIONS = [
  { value: "updated", label: "Last modified" },
  { value: "name", label: "Name" },
  { value: "size", label: "Size" },
  { value: "type", label: "Document type" },
] as const;

type SortKey = (typeof SORT_OPTIONS)[number]["value"];

const LIST_COLUMNS = ["Name", "Document type", "Size", "Modified", "Status"];

export function FileExplorer() {
  const viewMode = useUIStore((s) => s.fileViewMode);
  const setViewMode = useUIStore((s) => s.setFileViewMode);
  const [sort, setSort] = useState<SortKey>("updated");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [dragging, setDragging] = useState(false);

  function explainUploadUnavailable() {
    const f = feature("upload");
    toast.info(`${f.label} arrive in Phase ${f.phase}`, {
      description: "Nothing was uploaded. Connect Google Drive first once it is available.",
    });
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    // Files are intentionally not read or stored anywhere until the upload
    // pipeline (with server-side validation) exists.
    explainUploadUnavailable();
  }

  return (
    <div className="flex flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b px-6 py-3">
        <nav aria-label="Breadcrumb" className="mr-auto flex items-center gap-1 text-sm">
          <HardDrive className="size-4 text-muted-foreground" aria-hidden="true" />
          <span className="font-medium">My Vault</span>
          <ChevronRight className="size-3.5 text-muted-foreground" aria-hidden="true" />
          <span className="text-muted-foreground">All files</span>
        </nav>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" aria-label="Filter by document type">
              <ListFilter />
              {typeFilter === "all"
                ? "All types"
                : DOCUMENT_TYPE_LABELS[typeFilter as keyof typeof DOCUMENT_TYPE_LABELS]}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="max-h-80 overflow-y-auto">
            <DropdownMenuLabel>Document type</DropdownMenuLabel>
            <DropdownMenuRadioGroup value={typeFilter} onValueChange={setTypeFilter}>
              <DropdownMenuRadioItem value="all">All types</DropdownMenuRadioItem>
              <DropdownMenuSeparator />
              {Object.entries(DOCUMENT_TYPE_LABELS).map(([value, label]) => (
                <DropdownMenuRadioItem key={value} value={value}>
                  {label}
                </DropdownMenuRadioItem>
              ))}
            </DropdownMenuRadioGroup>
          </DropdownMenuContent>
        </DropdownMenu>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" aria-label="Sort files">
              <ArrowDownUp />
              {SORT_OPTIONS.find((o) => o.value === sort)?.label}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>Sort by</DropdownMenuLabel>
            <DropdownMenuRadioGroup value={sort} onValueChange={(v) => setSort(v as SortKey)}>
              {SORT_OPTIONS.map((o) => (
                <DropdownMenuRadioItem key={o.value} value={o.value}>
                  {o.label}
                </DropdownMenuRadioItem>
              ))}
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

        <Button variant="outline" size="sm" onClick={explainUploadUnavailable} aria-disabled="true">
          <FolderPlus />
          New folder
        </Button>
        <Button size="sm" onClick={explainUploadUnavailable} aria-disabled="true">
          <Upload />
          Upload
        </Button>
      </div>

      {viewMode === "list" ? (
        <div role="table" aria-label="Files" className="border-b">
          <div
            role="row"
            className="grid grid-cols-[minmax(0,3fr)_minmax(0,1.3fr)_90px_120px_100px] gap-4 px-6 py-2 text-xs font-medium text-muted-foreground"
          >
            {LIST_COLUMNS.map((c) => (
              <span role="columnheader" key={c} className="truncate">
                {c}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      <div className="p-6">
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={cn(
            "rounded-xl border-2 border-dashed transition-colors",
            dragging ? "border-primary bg-accent/50" : "border-border",
          )}
        >
          <EmptyState
            icon={Upload}
            title="Your vault is empty"
            description={
              <>
                Drag files here or use <span className="font-medium text-foreground">Upload</span>.
                PDFs, Office documents, images, text and ZIP archives are supported.
              </>
            }
          />
        </div>
        <FeatureNotice featureKey="files" className="mt-4" />
      </div>
    </div>
  );
}
