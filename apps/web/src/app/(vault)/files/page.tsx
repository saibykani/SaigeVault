import type { Metadata } from "next";
import { Suspense } from "react";

import { PageHeader } from "@/components/common/page-header";
import { FileExplorer } from "@/components/files/file-explorer";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = { title: "Files" };

export default function FilesPage() {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader
        title="Files"
        description="Browse and manage every document in your vault. Originals stay in Google Drive."
      />
      <Suspense fallback={<Skeleton className="m-6 h-96" />}>
        <FileExplorer />
      </Suspense>
    </div>
  );
}
