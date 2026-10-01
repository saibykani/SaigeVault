import { CalendarClock } from "lucide-react";
import type { Metadata } from "next";

import { EmptyState } from "@/components/common/empty-state";
import { FeatureNotice } from "@/components/common/feature-notice";
import { PageHeader } from "@/components/common/page-header";

export const metadata: Metadata = { title: "Timeline" };

export default function TimelinePage() {
  return (
    <>
      <PageHeader
        title="Timeline"
        description="Your documents arranged in time — education, employment, certificates and more."
      />
      <div className="flex flex-col gap-4 p-6">
        <div className="rounded-xl border">
          <EmptyState
            icon={CalendarClock}
            title="Nothing on your timeline yet"
            description="The timeline is built only from dates extracted from your documents or confirmed by you. Saige never invents dates."
          />
        </div>
        <FeatureNotice featureKey="timeline" />
      </div>
    </>
  );
}
