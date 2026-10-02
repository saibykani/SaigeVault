"use client";

import { formatBytes, formatRelativeTime } from "@saige/shared";
import { FileText, HardDrive, Image as ImageIcon, Loader, Star, Upload } from "lucide-react";
import Link from "next/link";

import { EmptyState } from "@/components/common/empty-state";
import { FileIcon } from "@/components/files/file-icon";
import { openFilePicker } from "@/components/files/upload-manager";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useSession, useStorageConnections } from "@/lib/api";
import { useFiles, useFileStats } from "@/lib/files-api";

export function VaultMetrics() {
  const { data: session } = useSession();
  const { data: stats, isLoading } = useFileStats(Boolean(session));
  const metrics = [
    { label: "Files", icon: FileText, value: stats?.total_files },
    {
      label: "Storage used",
      icon: HardDrive,
      value: stats ? formatBytes(stats.total_bytes) : undefined,
    },
    { label: "Images", icon: ImageIcon, value: stats?.images },
    { label: "Awaiting processing", icon: Loader, value: stats?.pending_processing },
  ];
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {metrics.map(({ label, icon: Icon, value }) => (
        <Card key={label} className="px-4 py-3">
          <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
            <Icon className="size-3.5" aria-hidden="true" />
            {label}
          </div>
          {isLoading ? (
            <Skeleton className="mt-2 h-7 w-16" />
          ) : (
            <p className="mt-1.5 text-2xl font-semibold tabular-nums">{value ?? "—"}</p>
          )}
        </Card>
      ))}
    </div>
  );
}

export function RecentFiles() {
  const { data: session } = useSession();
  const { data: connections } = useStorageConnections(Boolean(session));
  const driveReady = connections?.some((c) => c.status === "active") ?? false;
  const { data, isLoading } = useFiles(
    { all_folders: true, sort: "updated", order: "desc", limit: 6 },
    Boolean(session),
  );
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Recent files</CardTitle>
          <CardDescription className="mt-1">Recently added and changed documents.</CardDescription>
        </div>
        <Button size="sm" variant="ghost" asChild>
          <Link href="/files">View all</Link>
        </Button>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 4 }, (_, i) => (
              <Skeleton key={i} className="h-9" />
            ))}
          </div>
        ) : data?.files.length ? (
          <ul className="divide-y rounded-md border">
            {data.files.map((f) => (
              <li key={f.id}>
                <Link
                  href={`/files/${f.id}`}
                  className="flex items-center gap-3 px-3 py-2.5 text-sm hover:bg-muted/60"
                >
                  <FileIcon extension={f.extension} />
                  <span className="min-w-0 flex-1 truncate">{f.name}</span>
                  {f.is_starred ? (
                    <Star className="size-3.5 fill-warning text-warning" aria-label="Starred" />
                  ) : null}
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {formatRelativeTime(new Date(f.updated_at))}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState
            icon={FileText}
            title="No files yet"
            description={
              driveReady
                ? "Upload your first document — a resume, certificate or payslip."
                : "Connect Google Drive in Settings, then upload your first document."
            }
            className="py-8"
          >
            {driveReady ? (
              <Button size="sm" onClick={openFilePicker}>
                <Upload />
                Upload
              </Button>
            ) : (
              <Button size="sm" asChild>
                <Link href="/settings#storage">Connect Google Drive</Link>
              </Button>
            )}
          </EmptyState>
        )}
      </CardContent>
    </Card>
  );
}
