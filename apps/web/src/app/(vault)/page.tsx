import {
  FileText,
  HardDrive,
  Image as ImageIcon,
  Library,
  ShieldCheck,
  Sparkles,
  Star,
} from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { SetupChecklist } from "@/components/dashboard/setup-checklist";
import { EmptyState } from "@/components/common/empty-state";
import { FeatureNotice } from "@/components/common/feature-notice";
import { PageHeader } from "@/components/common/page-header";
import { ReadinessPanel } from "@/components/system/readiness-panel";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export const metadata: Metadata = { title: "Dashboard" };

const METRICS = [
  { label: "Files", icon: FileText },
  { label: "Storage used", icon: HardDrive },
  { label: "Images", icon: ImageIcon },
  { label: "AI indexed", icon: Sparkles },
] as const;

export default function DashboardPage() {
  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Everything in your vault at a glance."
        actions={
          <Button asChild variant="outline" size="sm">
            <Link href="/ask">
              <Sparkles />
              Ask Saige
            </Link>
          </Button>
        }
      />
      <div className="grid gap-4 p-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="flex min-w-0 flex-col gap-4">
          {/* Metrics show "—" until the files API exists: no invented numbers. */}
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {METRICS.map(({ label, icon: Icon }) => (
              <Card key={label} className="px-4 py-3">
                <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                  <Icon className="size-3.5" aria-hidden="true" />
                  {label}
                </div>
                <p
                  className="mt-1.5 text-2xl font-semibold tabular-nums"
                  aria-label={`${label}: no data yet`}
                >
                  —
                </p>
              </Card>
            ))}
          </div>

          <Card>
            <CardHeader>
              <div>
                <CardTitle>Recent files</CardTitle>
                <CardDescription className="mt-1">
                  Recently added and opened documents.
                </CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              <EmptyState
                icon={FileText}
                title="No files yet"
                description="Once Google Drive is connected, your recent documents appear here."
                className="py-8"
              />
              <FeatureNotice featureKey="files" />
            </CardContent>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Star className="size-4 text-muted-foreground" aria-hidden="true" /> Favorites
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                Star important documents — passport, degree, latest payslip — for one-tap access.
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Library className="size-4 text-muted-foreground" aria-hidden="true" />{" "}
                  Collections
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                Group documents virtually, e.g. <em>My Career</em> or <em>Finance</em>, without
                duplicating files.
              </CardContent>
            </Card>
          </div>
        </div>

        <aside className="flex min-w-0 flex-col gap-4">
          <SetupChecklist />
          <ReadinessPanel compact />
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ShieldCheck className="size-4 text-primary" aria-hidden="true" /> Your data, your
                control
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-[13px] text-muted-foreground">
              <p>
                Original files stay in your own Google Drive. Saige stores references and metadata.
              </p>
              <p>
                AI answers cite their sources. Extracted data is marked AI-extracted until you
                confirm it.
              </p>
              <p>Your documents are never used to train models.</p>
            </CardContent>
          </Card>
        </aside>
      </div>
    </>
  );
}
