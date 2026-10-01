import type { Metadata } from "next";

import { PageHeader } from "@/components/common/page-header";
import { ReadinessPanel } from "@/components/system/readiness-panel";

export const metadata: Metadata = { title: "System status" };

export default function SystemPage() {
  return (
    <>
      <PageHeader
        title="System status"
        description="Live health of the services behind your vault. Refreshes every 15 seconds."
      />
      <div className="mx-auto w-full max-w-3xl p-6">
        <ReadinessPanel />
        <p className="mt-4 text-[13px] text-muted-foreground">
          PostgreSQL and Redis are critical: if either is down the vault is unavailable. Qdrant and
          the background worker are optional: file management keeps working while AI features and
          document processing pause.
        </p>
      </div>
    </>
  );
}
