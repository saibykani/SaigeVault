import { Library, ShieldCheck, Sparkles, Star } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { SetupChecklist } from "@/components/dashboard/setup-checklist";
import { RecentFiles, VaultMetrics } from "@/components/dashboard/vault-overview";
import { PageHeader } from "@/components/common/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export const metadata: Metadata = { title: "Dashboard" };

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
          <VaultMetrics />
          <RecentFiles />

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Star className="size-4 text-muted-foreground" aria-hidden="true" /> Favorites
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                Star important documents — passport, degree, latest payslip — for one-tap access.{" "}
                <Link href="/files?view=starred" className="text-primary hover:underline">
                  View starred
                </Link>
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
                duplicating files.{" "}
                <Link href="/collections" className="text-primary hover:underline">
                  Open collections
                </Link>
              </CardContent>
            </Card>
          </div>
        </div>

        <aside className="flex min-w-0 flex-col gap-4">
          <SetupChecklist />
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
