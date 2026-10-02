import type { Metadata } from "next";

import { CollectionsView } from "@/components/collections/collections-view";
import { PageHeader } from "@/components/common/page-header";

export const metadata: Metadata = { title: "Collections" };

export default function CollectionsPage() {
  return (
    <>
      <PageHeader
        title="Collections"
        description="Virtual groupings. A file can belong to many collections without being duplicated."
      />
      <CollectionsView />
    </>
  );
}
