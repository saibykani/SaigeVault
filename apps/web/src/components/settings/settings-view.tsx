"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import type * as React from "react";
import { Suspense } from "react";

import { FeatureNotice } from "@/components/common/feature-notice";
import { useMounted } from "@/components/shell/theme-toggle";
import { Badge } from "@/components/ui/badge";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { Skeleton } from "@/components/ui/skeleton";
import { AccountSecurity } from "@/components/settings/account-security";
import { DriveConnection } from "@/components/settings/drive-connection";
import { SessionsList } from "@/components/settings/sessions-list";
import { useSystemInfo } from "@/lib/api";

function Section({
  id,
  title,
  description,
  children,
}: {
  id: string;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section
      id={id}
      aria-labelledby={`${id}-title`}
      className="grid scroll-mt-20 gap-4 border-b py-6 last:border-b-0 md:grid-cols-[240px_minmax(0,1fr)]"
    >
      <div>
        <h2 id={`${id}-title`} className="text-sm font-semibold">
          {title}
        </h2>
        <p className="mt-1 text-[13px] text-muted-foreground">{description}</p>
      </div>
      <div className="min-w-0 space-y-3">{children}</div>
    </section>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-md border px-3 py-2.5 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="min-w-0 truncate text-right font-medium">{children}</span>
    </div>
  );
}

const POLICY_LABEL = {
  disabled: { text: "Disabled", variant: "default" },
  local_only: { text: "Local models only", variant: "success" },
  third_party_allowed: { text: "Third-party providers allowed", variant: "warning" },
} as const;

export function SettingsView() {
  const { theme, setTheme } = useTheme();
  const mounted = useMounted();
  const { data: info, isLoading } = useSystemInfo();

  return (
    <div className="mx-auto w-full max-w-4xl px-6">
      <Section
        id="appearance"
        title="Appearance"
        description="Choose how Saige Vault looks on this device."
      >
        <SegmentedControl
          ariaLabel="Theme"
          value={(mounted ? theme : "system") as "light" | "dark" | "system"}
          onValueChange={setTheme}
          options={[
            { value: "light", label: "Light", icon: Sun },
            { value: "dark", label: "Dark", icon: Moon },
            { value: "system", label: "System", icon: Monitor },
          ]}
        />
      </Section>

      <Section
        id="privacy"
        title="AI & privacy"
        description="Where your document content is allowed to go. Set by the server administrator."
      >
        {isLoading ? (
          <Skeleton className="h-11" />
        ) : (
          <Row label="AI processing policy">
            {info ? (
              <Badge variant={POLICY_LABEL[info.ai_processing_policy].variant}>
                {POLICY_LABEL[info.ai_processing_policy].text}
              </Badge>
            ) : (
              "Unavailable"
            )}
          </Row>
        )}
        <ul className="space-y-1.5 text-[13px] text-muted-foreground">
          <li>· Your documents are never used to train AI models.</li>
          <li>· Content is only sent to an AI provider permitted by this policy.</li>
          <li>· Instructions inside documents are treated as data, never as commands.</li>
        </ul>
      </Section>

      <Section
        id="storage"
        title="Storage"
        description="Saige keeps your original files in your own cloud storage."
      >
        <Suspense fallback={<Skeleton className="h-28" />}>
          <DriveConnection />
        </Suspense>
      </Section>

      <Section
        id="security"
        title="Security"
        description="Password, two-step verification, and the devices signed in to your vault. Revoke any you don't recognise."
      >
        <AccountSecurity />
        <SessionsList />
      </Section>

      <Section
        id="data"
        title="Your data"
        description="You are never locked in. Files always remain in your own storage."
      >
        <FeatureNotice featureKey="export" />
      </Section>

      <Section id="about" title="About" description="Server and client versions.">
        <Row label="API version">{info ? `v${info.version}` : "—"}</Row>
        <Row label="Environment">{info?.environment ?? "—"}</Row>
        <Row label="Web client">v0.1.0</Row>
      </Section>
    </div>
  );
}
