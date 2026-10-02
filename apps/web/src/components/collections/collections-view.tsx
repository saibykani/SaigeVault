"use client";

import { formatRelativeTime } from "@saige/shared";
import { Briefcase, FolderKanban, GraduationCap, Library, Plus, Wallet } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/common/empty-state";
import { NameDialog } from "@/components/files/dialogs";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useSession } from "@/lib/api";
import { errorMessage, useCollections, useCreateCollection } from "@/lib/files-api";

const TEMPLATES = [
  { name: "My Career", icon: Briefcase, hint: "Resume, certificates, offer & experience letters" },
  { name: "Finance", icon: Wallet, hint: "Payslips, tax, bank statements" },
  { name: "Education", icon: GraduationCap, hint: "Degree, diploma, certificates" },
  { name: "Projects", icon: FolderKanban, hint: "QA, JMeter, automation notes" },
];

export function CollectionsView() {
  const { data: session } = useSession();
  const { data: collections, isLoading } = useCollections(Boolean(session));
  const create = useCreateCollection();
  const [creating, setCreating] = useState(false);
  const existing = new Set((collections ?? []).map((c) => c.name.toLowerCase()));

  function make(name: string, onDone?: () => void) {
    create.mutate(
      { name },
      {
        onSuccess: (c) => {
          onDone?.();
          toast.success(`Created ${c.name}`);
        },
        onError: (e) => toast.error(errorMessage(e, "Couldn't create collection")),
      },
    );
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setCreating(true)}>
          <Plus />
          New collection
        </Button>
      </div>

      {isLoading ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      ) : collections?.length ? (
        <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {collections.map((c) => (
            <li key={c.id}>
              <Link href={`/collections/${c.id}`} className="block h-full">
                <Card className="h-full p-4 transition-colors hover:bg-muted/50">
                  <div className="flex items-center gap-2">
                    <span className="flex size-8 items-center justify-center rounded-md bg-accent text-accent-foreground">
                      <Library className="size-4" aria-hidden="true" />
                    </span>
                    <h3 className="truncate text-sm font-semibold">{c.name}</h3>
                  </div>
                  <p className="mt-3 text-xs text-muted-foreground">
                    {c.file_count} file{c.file_count === 1 ? "" : "s"} · updated{" "}
                    {formatRelativeTime(new Date(c.updated_at))}
                  </p>
                </Card>
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <div className="rounded-xl border">
          <EmptyState
            icon={Library}
            title="No collections yet"
            description="Collections group files virtually — one file can be in many collections without being copied. Start from a template below."
          />
        </div>
      )}

      <section aria-labelledby="templates-heading">
        <h2 id="templates-heading" className="mb-3 text-sm font-semibold">
          Quick start
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {TEMPLATES.map(({ name, icon: Icon, hint }) => {
            const exists = existing.has(name.toLowerCase());
            return (
              <Card key={name} className="flex flex-col p-4">
                <div className="flex items-center gap-2">
                  <span className="flex size-8 items-center justify-center rounded-md bg-accent text-accent-foreground">
                    <Icon className="size-4" aria-hidden="true" />
                  </span>
                  <h3 className="text-sm font-semibold">{name}</h3>
                </div>
                <p className="mt-2 flex-1 text-[13px] text-muted-foreground">{hint}</p>
                <Button
                  size="sm"
                  variant="outline"
                  className="mt-3 self-start"
                  disabled={exists || create.isPending}
                  onClick={() => make(name)}
                >
                  {exists ? "Created" : "Create"}
                </Button>
              </Card>
            );
          })}
        </div>
      </section>

      {creating ? (
        <NameDialog
          open
          onOpenChange={setCreating}
          title="New collection"
          label="Collection name"
          submitLabel="Create"
          pending={create.isPending}
          onSubmit={(name) => make(name, () => setCreating(false))}
        />
      ) : null}
    </div>
  );
}
