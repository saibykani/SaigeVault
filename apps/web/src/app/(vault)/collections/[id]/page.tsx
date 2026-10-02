import type { Metadata } from "next";

import { CollectionDetail } from "@/components/collections/collection-detail";

export const metadata: Metadata = { title: "Collection" };

export default async function CollectionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <CollectionDetail id={id} />;
}
