"use client";

import type { FileSummary, FolderSummary } from "@saige/api-client";
import { useState } from "react";
import { toast } from "sonner";

import {
  errorMessage,
  useAddToCollection,
  useBulk,
  useDeleteFolder,
  useDeleteForever,
  useSetTags,
  useUpdateFile,
  useUpdateFolder,
} from "@/lib/files-api";

import {
  CollectionPickerDialog,
  ConfirmDialog,
  MoveDialog,
  NameDialog,
  TagsDialog,
} from "./dialogs";

type DialogState =
  | { type: "rename"; file: FileSummary }
  | { type: "renameFolder"; folder: FolderSummary }
  | { type: "move"; fileIds: string[] }
  | { type: "moveFolder"; folder: FolderSummary }
  | { type: "tags"; file: FileSummary }
  | { type: "collection"; fileIds: string[] }
  | { type: "deleteForever"; files: FileSummary[] }
  | { type: "deleteFolder"; folder: FolderSummary }
  | null;

/** Shared file actions + their dialogs, used by the explorer, collections and preview. */
export function useFileActions(options?: { onDone?: () => void }) {
  const [dialog, setDialog] = useState<DialogState>(null);
  const update = useUpdateFile();
  const bulk = useBulk();
  const deleteForever = useDeleteForever();
  const setTags = useSetTags();
  const updateFolder = useUpdateFolder();
  const deleteFolder = useDeleteFolder();
  const addToCollection = useAddToCollection();

  const close = () => setDialog(null);
  const done = () => {
    close();
    options?.onDone?.();
  };

  async function trash(fileIds: string[]) {
    try {
      const result = await bulk.mutateAsync({ file_ids: fileIds, action: "trash" });
      options?.onDone?.();
      toast.success(
        `${result.succeeded.length} item${result.succeeded.length === 1 ? "" : "s"} moved to trash`,
        {
          action: {
            label: "Undo",
            onClick: () => void restore(result.succeeded),
          },
        },
      );
      if (result.failed.length) toast.error(`${result.failed.length} couldn't be moved to trash`);
    } catch (error) {
      toast.error(errorMessage(error, "Couldn't move to trash"));
    }
  }

  async function restore(fileIds: string[]) {
    try {
      const result = await bulk.mutateAsync({ file_ids: fileIds, action: "restore" });
      options?.onDone?.();
      toast.success(`${result.succeeded.length} restored`);
    } catch (error) {
      toast.error(errorMessage(error, "Couldn't restore"));
    }
  }

  async function star(fileIds: string[], starred: boolean) {
    try {
      await bulk.mutateAsync({ file_ids: fileIds, action: starred ? "star" : "unstar" });
    } catch (error) {
      toast.error(errorMessage(error));
    }
  }

  const dialogs = (
    <>
      {dialog?.type === "rename" ? (
        <NameDialog
          open
          onOpenChange={close}
          title="Rename file"
          label="Name"
          initial={dialog.file.name}
          submitLabel="Rename"
          pending={update.isPending}
          onSubmit={(name) =>
            update.mutate(
              { id: dialog.file.id, patch: { name } },
              { onSuccess: done, onError: (e) => toast.error(errorMessage(e, "Couldn't rename")) },
            )
          }
        />
      ) : null}
      {dialog?.type === "renameFolder" ? (
        <NameDialog
          open
          onOpenChange={close}
          title="Rename folder"
          label="Name"
          initial={dialog.folder.name}
          submitLabel="Rename"
          pending={updateFolder.isPending}
          onSubmit={(name) =>
            updateFolder.mutate(
              { id: dialog.folder.id, patch: { name } },
              { onSuccess: done, onError: (e) => toast.error(errorMessage(e, "Couldn't rename")) },
            )
          }
        />
      ) : null}
      {dialog?.type === "move" ? (
        <MoveDialog
          open
          onOpenChange={close}
          pending={bulk.isPending}
          onMove={(folderId) =>
            bulk.mutate(
              {
                file_ids: dialog.fileIds,
                action: "move",
                ...(folderId ? { folder_id: folderId } : {}),
              },
              {
                onSuccess: (r) => {
                  done();
                  toast.success(`${r.succeeded.length} moved`);
                },
                onError: (e) => toast.error(errorMessage(e, "Couldn't move")),
              },
            )
          }
        />
      ) : null}
      {dialog?.type === "moveFolder" ? (
        <MoveDialog
          open
          onOpenChange={close}
          excludeFolderId={dialog.folder.id}
          pending={updateFolder.isPending}
          onMove={(folderId) =>
            updateFolder.mutate(
              {
                id: dialog.folder.id,
                patch: folderId ? { parent_id: folderId } : { move_to_root: true },
              },
              { onSuccess: done, onError: (e) => toast.error(errorMessage(e, "Couldn't move")) },
            )
          }
        />
      ) : null}
      {dialog?.type === "tags" ? (
        <TagsDialog
          open
          onOpenChange={close}
          initial={dialog.file.tags?.map((t) => t.name) ?? []}
          pending={setTags.isPending}
          onSave={(names) =>
            setTags.mutate(
              { id: dialog.file.id, names },
              {
                onSuccess: done,
                onError: (e) => toast.error(errorMessage(e, "Couldn't save tags")),
              },
            )
          }
        />
      ) : null}
      {dialog?.type === "collection" ? (
        <CollectionPickerDialog
          open
          onOpenChange={close}
          pending={addToCollection.isPending}
          onPick={(collectionId) =>
            addToCollection.mutate(
              { id: collectionId, fileIds: dialog.fileIds },
              {
                onSuccess: (c) => {
                  done();
                  toast.success(`Added to ${c.name}`);
                },
                onError: (e) => toast.error(errorMessage(e, "Couldn't add to collection")),
              },
            )
          }
        />
      ) : null}
      {dialog?.type === "deleteForever" ? (
        <ConfirmDialog
          open
          onOpenChange={close}
          destructive
          title={`Delete ${dialog.files.length === 1 ? `“${dialog.files[0]!.name}”` : `${dialog.files.length} files`} forever?`}
          description="This permanently deletes the file from your Google Drive as well. It can't be undone."
          confirmLabel="Delete forever"
          pending={deleteForever.isPending}
          onConfirm={async () => {
            let ok = 0;
            for (const f of dialog.files) {
              try {
                await deleteForever.mutateAsync(f.id);
                ok += 1;
              } catch (e) {
                toast.error(errorMessage(e, `Couldn't delete ${f.name}`));
              }
            }
            done();
            if (ok) toast.success(`${ok} deleted permanently`);
          }}
        />
      ) : null}
      {dialog?.type === "deleteFolder" ? (
        <ConfirmDialog
          open
          onOpenChange={close}
          destructive
          title={`Delete folder “${dialog.folder.name}”?`}
          description="Only empty folders can be deleted. The folder is moved to your Google Drive trash."
          confirmLabel="Delete folder"
          pending={deleteFolder.isPending}
          onConfirm={() =>
            deleteFolder.mutate(dialog.folder.id, {
              onSuccess: done,
              onError: (e) => toast.error(errorMessage(e, "Couldn't delete folder")),
            })
          }
        />
      ) : null}
    </>
  );

  return { open: setDialog, trash, restore, star, dialogs, busy: bulk.isPending };
}
