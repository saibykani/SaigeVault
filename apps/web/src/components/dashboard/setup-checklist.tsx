"use client";

import { CheckCircle2, Circle, CircleDashed } from "lucide-react";
import Link from "next/link";
import type * as React from "react";

import { PhaseBadge } from "@/components/common/feature-notice";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useSession, useSystemInfo } from "@/lib/api";
import type { FeatureKey } from "@/lib/features";
import { cn } from "@/lib/utils";

type StepState = "done" | "todo" | "blocked";

interface Step {
  title: string;
  detail: React.ReactNode;
  state: StepState;
  href?: string;
  feature?: FeatureKey;
}

const POLICY_COPY = {
  disabled: "AI processing is disabled — no document content leaves this server.",
  local_only: "AI runs on local models only — content never leaves this deployment.",
  third_party_allowed: "Third-party AI providers are allowed by server policy.",
} as const;

function StepIcon({ state }: { state: StepState }) {
  if (state === "done") return <CheckCircle2 className="size-4 text-success" aria-label="Done" />;
  if (state === "blocked")
    return <CircleDashed className="size-4 text-muted-foreground" aria-label="Not yet available" />;
  return <Circle className="size-4 text-muted-foreground" aria-label="To do" />;
}

export function SetupChecklist() {
  const { data: info, isError } = useSystemInfo();
  const { data: session } = useSession();

  const steps: Step[] = [
    {
      title: "Server running",
      detail: isError
        ? "The API is unreachable."
        : info
          ? `Saige API v${info.version} (${info.environment}).`
          : "Checking…",
      state: info ? "done" : "todo",
      href: "/system",
    },
    {
      title: "Google OAuth configured",
      detail: info?.google_oauth_configured
        ? "Client credentials are set on the server."
        : "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET on the server.",
      state: info?.google_oauth_configured ? "done" : "todo",
    },
    {
      title: "Signed in",
      detail: session ? `As ${session.user.email}` : "Sign in with your Google account.",
      state: session ? "done" : "todo",
      href: session ? "/settings#security" : "/login",
    },
    {
      title: "Connect Google Drive",
      detail: "Your files stay in your Drive; Saige stores references and metadata.",
      state: "blocked",
      feature: "googleDrive",
    },
    {
      title: "Review AI & privacy policy",
      detail: info
        ? POLICY_COPY[info.ai_processing_policy]
        : isError
          ? "Unavailable while the API is unreachable."
          : "Checking…",
      state: info ? "done" : "todo",
      href: "/settings#privacy",
    },
  ];

  const done = steps.filter((s) => s.state === "done").length;

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Set up your vault</CardTitle>
          <CardDescription className="mt-1">
            {done} of {steps.length} steps complete
          </CardDescription>
        </div>
        <div
          className="mt-1 h-1.5 w-24 overflow-hidden rounded-full bg-muted"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={steps.length}
          aria-valuenow={done}
          aria-label="Setup progress"
        >
          <div
            className="h-full rounded-full bg-primary transition-all"
            style={{ width: `${(done / steps.length) * 100}%` }}
          />
        </div>
      </CardHeader>
      <CardContent className="pt-3">
        <ol className="divide-y rounded-md border">
          {steps.map((step) => {
            const body = (
              <>
                <StepIcon state={step.state} />
                <div className="min-w-0 flex-1">
                  <p
                    className={cn(
                      "text-sm font-medium",
                      step.state === "blocked" && "text-muted-foreground",
                    )}
                  >
                    {step.title}
                  </p>
                  <p className="truncate text-xs text-muted-foreground">{step.detail}</p>
                </div>
                {step.feature ? <PhaseBadge featureKey={step.feature} /> : null}
              </>
            );
            return (
              <li key={step.title}>
                {step.href ? (
                  <Link
                    href={step.href}
                    className="flex items-center gap-3 px-3 py-2.5 hover:bg-muted/60"
                  >
                    {body}
                  </Link>
                ) : (
                  <div className="flex items-center gap-3 px-3 py-2.5">{body}</div>
                )}
              </li>
            );
          })}
        </ol>
      </CardContent>
    </Card>
  );
}
