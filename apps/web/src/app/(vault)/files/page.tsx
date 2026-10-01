import type { Metadata } from "next";

import { PageHeader } from "@/components/common/page-header";
import { FileExplorer } from "@/components/files/file-explorer";

export const metadata: Metadata = { title: "Files" };

export default function FilesPage() {
  return (
    <>
      <PageHeader
        title="Files"
        description="Browse and manage every document in your vault. Originals stay in Google Drive."
      />
      <FileExplorer />
    </>
  );
}
