import { Briefcase, FolderKanban, GraduationCap, Library, Plus, Wallet } from "lucide-react";
import type { Metadata } from "next";

import { EmptyState } from "@/components/common/empty-state";
import { FeatureNotice } from "@/components/common/feature-notice";
import { PageHeader } from "@/components/common/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export const metadata: Metadata = { title: "Collections" };

const TEMPLATES = [
  {
    name: "My Career",
    icon: Briefcase,
    items: ["Resume", "Certificates", "Offer letters", "Experience letters"],
  },
  { name: "Finance", icon: Wallet, items: ["Payslips", "Tax", "Bank statements"] },
  { name: "Education", icon: GraduationCap, items: ["Degree", "Diploma", "Certificates"] },
  { name: "Projects", icon: FolderKanban, items: ["QA", "JMeter", "Automation"] },
];

export default function CollectionsPage() {
  return (
    <>
      <PageHeader
        title="Collections"
        description="Virtual groupings. A file can belong to many collections without being duplicated."
        actions={
          <Button size="sm" disabled>
            <Plus />
            New collection
          </Button>
        }
      />
      <div className="flex flex-col gap-6 p-6">
        <div className="rounded-xl border">
          <EmptyState
            icon={Library}
            title="No collections yet"
            description="Start from a template below or create your own once file management is available."
          />
        </div>
        <section aria-labelledby="templates-heading">
          <h2 id="templates-heading" className="mb-3 text-sm font-semibold">
            Suggested templates
          </h2>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {TEMPLATES.map(({ name, icon: Icon, items }) => (
              <Card key={name} className="p-4">
                <div className="flex items-center gap-2">
                  <span className="flex size-8 items-center justify-center rounded-md bg-accent text-accent-foreground">
                    <Icon className="size-4" aria-hidden="true" />
                  </span>
                  <h3 className="text-sm font-semibold">{name}</h3>
                </div>
                <ul className="mt-3 space-y-1 text-[13px] text-muted-foreground">
                  {items.map((item) => (
                    <li key={item}>· {item}</li>
                  ))}
                </ul>
              </Card>
            ))}
          </div>
        </section>
        <FeatureNotice featureKey="collections" />
      </div>
    </>
  );
}
