"use client";

import { formatBytes, formatRelativeTime } from "@saige/shared";
import { Library, MinusCircle, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/common/empty-state";
import { PageHeader } from "@/components/common/page-header";
import { ConfirmDialog } from "@/components/files/dialogs";
import { FileIcon } from "@/components/files/file-icon";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  errorMessage,
  useCollection,
  useDeleteCollection,
  useRemoveFromCollection,
} from "@/lib/files-api";

export function CollectionDetail({ id }: { id: string }) {
  const router = useRouter();
  const { data, isLoading, isError } = useCollection(id);
  const remove = useRemoveFromCollection();
  const destroy = useDeleteCollection();
  const [confirming, setConfirming] = useState(false);

  if (isLoading) return <Skeleton className="m-6 h-72" />;
  if (isError || !data) {
    return (
      <EmptyState
        icon={Library}
        title="Collection not found"
        description="It may have been deleted."
      >
        <Button size="sm" asChild>
          <Link href="/collections">All collections</Link>
        </Button>
      </EmptyState>
    );
  }
  const { collection, files } = data;

  return (
    <>
      <PageHeader
        title={collection.name}
        description={`${collection.file_count} file${collection.file_count === 1 ? "" : "s"}. Removing a file here never deletes it.`}
        actions={
          <Button size="sm" variant="outline" onClick={() => setConfirming(true)}>
            <Trash2 />
            Delete collection
          </Button>
        }
      />
      {files.length === 0 ? (
        <EmptyState
          icon={Library}
          title="This collection is empty"
          description="Add files from the Files page: open a file's menu and choose “Add to collection”."
        >
          <Button size="sm" asChild>
            <Link href="/files">Go to files</Link>
          </Button>
        </EmptyState>
      ) : (
        <ul className="divide-y">
          {files.map((f) => (
            <li key={f.id} className="flex items-center gap-3 px-6 py-2.5 text-sm">
              <FileIcon extension={f.extension} />
              <Link href={`/files/${f.id}`} className="min-w-0 flex-1 truncate hover:underline">
                {f.name}
              </Link>
              <span className="hidden text-muted-foreground tabular-nums sm:block">
                {formatBytes(f.size_bytes)}
              </span>
              <span className="hidden w-28 text-muted-foreground md:block">
                {formatRelativeTime(new Date(f.updated_at))}
              </span>
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label={`Remove ${f.name} from collection`}
                onClick={() =>
                  remove.mutate(
                    { id, fileId: f.id },
                    { onError: (e) => toast.error(errorMessage(e, "Couldn't remove")) },
                  )
                }
              >
                <MinusCircle />
              </Button>
            </li>
          ))}
        </ul>
      )}
      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title={`Delete “${collection.name}”?`}
        description="The collection is removed. Its files stay in your vault and Google Drive."
        confirmLabel="Delete collection"
        destructive
        pending={destroy.isPending}
        onConfirm={() =>
          destroy.mutate(id, {
            onSuccess: () => {
              toast.success("Collection deleted");
              router.push("/collections");
            },
            onError: (e) => toast.error(errorMessage(e, "Couldn't delete")),
          })
        }
      />
    </>
  );
}
