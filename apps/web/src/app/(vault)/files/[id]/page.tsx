import type { Metadata } from "next";
import { Suspense } from "react";

import { FilePreview } from "@/components/files/file-preview";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = { title: "File" };

export default async function FilePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <Suspense fallback={<Skeleton className="m-6 h-[70vh]" />}>
      <FilePreview id={id} />
    </Suspense>
  );
}
