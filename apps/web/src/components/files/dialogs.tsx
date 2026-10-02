"use client";

import { ChevronRight, Folder, Library, Loader2, Plus } from "lucide-react";
import { type FormEvent, type ReactNode, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useCollections, useCreateCollection, useFiles, useTags } from "@/lib/files-api";
import { cn } from "@/lib/utils";

function Shell({
  open,
  onOpenChange,
  title,
  description,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="p-5">
        <DialogTitle>{title}</DialogTitle>
        {description ? (
          <DialogDescription className="mt-1.5">{description}</DialogDescription>
        ) : (
          <DialogDescription className="sr-only">{title}</DialogDescription>
        )}
        <div className="mt-4">{children}</div>
      </DialogContent>
    </Dialog>
  );
}

function Actions({ children }: { children: ReactNode }) {
  return <div className="mt-5 flex justify-end gap-2">{children}</div>;
}

export function NameDialog({
  open,
  onOpenChange,
  title,
  label,
  initial = "",
  submitLabel,
  pending,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  label: string;
  initial?: string;
  submitLabel: string;
  pending?: boolean;
  onSubmit: (value: string) => void;
}) {
  const [value, setValue] = useState(initial);
  function submit(event: FormEvent) {
    event.preventDefault();
    if (value.trim()) onSubmit(value.trim());
  }
  return (
    <Shell open={open} onOpenChange={onOpenChange} title={title}>
      <form onSubmit={submit}>
        <label htmlFor="name-input" className="text-sm font-medium">
          {label}
        </label>
        <Input
          id="name-input"
          autoFocus
          className="mt-1.5"
          value={value}
          maxLength={255}
          onChange={(e) => setValue(e.target.value)}
          onFocus={(e) => {
            // Select the name without its extension, like a desktop file manager.
            const dot = e.target.value.lastIndexOf(".");
            e.target.setSelectionRange(0, dot > 0 ? dot : e.target.value.length);
          }}
        />
        <Actions>
          <Button type="button" variant="outline" size="sm" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type="submit" size="sm" disabled={!value.trim() || pending}>
            {pending ? <Loader2 className="animate-spin" /> : null}
            {submitLabel}
          </Button>
        </Actions>
      </form>
    </Shell>
  );
}

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  destructive,
  pending,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel: string;
  destructive?: boolean;
  pending?: boolean;
  onConfirm: () => void;
}) {
  return (
    <Shell open={open} onOpenChange={onOpenChange} title={title} description={description}>
      <Actions>
        <Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>
          Cancel
        </Button>
        <Button
          variant={destructive ? "destructive" : "default"}
          size="sm"
          disabled={pending}
          onClick={onConfirm}
        >
          {pending ? <Loader2 className="animate-spin" /> : null}
          {confirmLabel}
        </Button>
      </Actions>
    </Shell>
  );
}

/** Folder picker: browse folders and choose a destination. */
export function MoveDialog({
  open,
  onOpenChange,
  excludeFolderId,
  pending,
  onMove,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  excludeFolderId?: string;
  pending?: boolean;
  onMove: (folderId: string | undefined) => void;
}) {
  const [current, setCurrent] = useState<string | undefined>(undefined);
  const { data, isLoading } = useFiles({ folder_id: current, limit: 1 }, open);
  const crumbs = data?.breadcrumbs ?? [{ id: null, name: "My Vault" }];

  return (
    <Shell open={open} onOpenChange={onOpenChange} title="Move to…">
      <nav aria-label="Destination" className="flex flex-wrap items-center gap-1 text-sm">
        {crumbs.map((c, i) => (
          <span key={c.id ?? "root"} className="flex items-center gap-1">
            {i > 0 ? <ChevronRight className="size-3.5 text-muted-foreground" /> : null}
            <button
              type="button"
              className={cn(
                "rounded px-1 hover:bg-muted",
                i === crumbs.length - 1 && "font-medium",
              )}
              onClick={() => setCurrent(c.id ?? undefined)}
            >
              {c.name}
            </button>
          </span>
        ))}
      </nav>
      <ul className="mt-3 max-h-64 divide-y overflow-y-auto rounded-md border">
        {isLoading ? (
          <li className="p-3">
            <Skeleton className="h-6" />
          </li>
        ) : data?.folders.length ? (
          data.folders
            .filter((f) => f.id !== excludeFolderId)
            .map((f) => (
              <li key={f.id}>
                <button
                  type="button"
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-muted"
                  onClick={() => setCurrent(f.id)}
                >
                  <Folder className="size-4 fill-primary/15 text-primary" aria-hidden="true" />
                  <span className="flex-1 truncate">{f.name}</span>
                  <ChevronRight className="size-3.5 text-muted-foreground" />
                </button>
              </li>
            ))
        ) : (
          <li className="px-3 py-4 text-center text-sm text-muted-foreground">No subfolders</li>
        )}
      </ul>
      <Actions>
        <Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>
          Cancel
        </Button>
        <Button size="sm" disabled={pending} onClick={() => onMove(current)}>
          {pending ? <Loader2 className="animate-spin" /> : null}
          Move here
        </Button>
      </Actions>
    </Shell>
  );
}

export function TagsDialog({
  open,
  onOpenChange,
  initial,
  pending,
  onSave,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initial: string[];
  pending?: boolean;
  onSave: (names: string[]) => void;
}) {
  const [tags, setTags] = useState<string[]>(initial);
  const [draft, setDraft] = useState("");
  const { data: existing } = useTags();
  const suggestions = (existing ?? [])
    .map((t) => t.name)
    .filter((n) => !tags.some((t) => t.toLowerCase() === n.toLowerCase()))
    .filter((n) => !draft || n.toLowerCase().includes(draft.toLowerCase().replace(/^#/, "")))
    .slice(0, 8);

  function add(name: string) {
    const clean = name.trim().replace(/^#/, "");
    if (clean && !tags.some((t) => t.toLowerCase() === clean.toLowerCase())) {
      setTags([...tags, clean.slice(0, 64)]);
    }
    setDraft("");
  }

  return (
    <Shell open={open} onOpenChange={onOpenChange} title="Tags">
      <div className="flex min-h-9 flex-wrap items-center gap-1.5 rounded-md border px-2 py-1.5">
        {tags.map((t) => (
          <Badge key={t} className="h-6 gap-1 pr-1 text-xs">
            #{t}
            <button
              type="button"
              aria-label={`Remove ${t}`}
              className="rounded px-0.5 hover:bg-background/60"
              onClick={() => setTags(tags.filter((x) => x !== t))}
            >
              ×
            </button>
          </Badge>
        ))}
        <input
          autoFocus
          aria-label="Add a tag"
          value={draft}
          placeholder={tags.length ? "" : "Add tags, e.g. career, 2026"}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === ",") {
              e.preventDefault();
              add(draft);
            } else if (e.key === "Backspace" && !draft && tags.length) {
              setTags(tags.slice(0, -1));
            }
          }}
          className="min-w-24 flex-1 bg-transparent text-sm outline-none"
        />
      </div>
      {suggestions.length ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {suggestions.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => add(s)}
              className="rounded-md border px-2 py-0.5 text-xs text-muted-foreground hover:bg-muted"
            >
              #{s}
            </button>
          ))}
        </div>
      ) : null}
      <Actions>
        <Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>
          Cancel
        </Button>
        <Button
          size="sm"
          disabled={pending}
          onClick={() => onSave(draft.trim() ? [...tags, draft.trim()] : tags)}
        >
          {pending ? <Loader2 className="animate-spin" /> : null}
          Save tags
        </Button>
      </Actions>
    </Shell>
  );
}

export function CollectionPickerDialog({
  open,
  onOpenChange,
  pending,
  onPick,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  pending?: boolean;
  onPick: (collectionId: string) => void;
}) {
  const { data: collections, isLoading } = useCollections(open);
  const create = useCreateCollection();
  const [name, setName] = useState("");

  return (
    <Shell open={open} onOpenChange={onOpenChange} title="Add to collection">
      <ul className="max-h-64 divide-y overflow-y-auto rounded-md border">
        {isLoading ? (
          <li className="p-3">
            <Skeleton className="h-6" />
          </li>
        ) : collections?.length ? (
          collections.map((c) => (
            <li key={c.id}>
              <button
                type="button"
                disabled={pending}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-muted"
                onClick={() => onPick(c.id)}
              >
                <Library className="size-4 text-muted-foreground" aria-hidden="true" />
                <span className="flex-1 truncate">{c.name}</span>
                <span className="text-xs text-muted-foreground">{c.file_count}</span>
              </button>
            </li>
          ))
        ) : (
          <li className="px-3 py-4 text-center text-sm text-muted-foreground">
            No collections yet
          </li>
        )}
      </ul>
      <form
        className="mt-3 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (!name.trim()) return;
          create.mutate(
            { name: name.trim() },
            {
              onSuccess: (created) => {
                setName("");
                onPick(created.id);
              },
            },
          );
        }}
      >
        <Input
          placeholder="New collection name"
          aria-label="New collection name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <Button
          type="submit"
          size="sm"
          variant="outline"
          disabled={!name.trim() || create.isPending}
        >
          <Plus />
          Create
        </Button>
      </form>
      {create.isError ? (
        <p className="mt-2 text-xs text-destructive">{create.error.message}</p>
      ) : null}
    </Shell>
  );
}
