import type { Metadata } from "next";

import { PageHeader } from "@/components/common/page-header";
import { SearchWorkspace } from "@/components/search/search-workspace";

export const metadata: Metadata = { title: "Search" };

export default function SearchPage() {
  return (
    <>
      <PageHeader
        title="Search"
        description="Exact, full-text, semantic and hybrid search across every document."
      />
      <SearchWorkspace />
    </>
  );
}
