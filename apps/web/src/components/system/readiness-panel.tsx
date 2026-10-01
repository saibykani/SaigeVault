"use client";

import { RefreshCw } from "lucide-react";

import { StatusDot } from "@/components/common/status-dot";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useReadiness } from "@/lib/api";

import { DEPENDENCY_LABELS, describeReadiness } from "./readiness";

export function ReadinessPanel({ compact = false }: { compact?: boolean }) {
  const { data, isError, isFetching, refetch, dataUpdatedAt } = useReadiness({
    refetchInterval: 15_000,
  });
  const view = describeReadiness(data, isError);

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle className="flex items-center gap-2">
            <StatusDot tone={view.tone} />
            {view.label}
          </CardTitle>
          <CardDescription className="mt-1">{view.summary}</CardDescription>
        </div>
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={() => void refetch()}
          aria-label="Refresh system status"
        >
          <RefreshCw className={isFetching ? "animate-spin" : undefined} />
        </Button>
      </CardHeader>
      <CardContent>
        {!data && !isError ? (
          <div className="space-y-2">
            {Array.from({ length: 4 }, (_, i) => (
              <Skeleton key={i} className="h-8" />
            ))}
          </div>
        ) : data ? (
          <ul className="divide-y rounded-md border">
            {data.checks.map((check) => (
              <li key={check.name} className="flex items-center gap-3 px-3 py-2 text-sm">
                <StatusDot tone={check.status === "ok" ? "ok" : check.critical ? "fail" : "warn"} />
                <span className="font-medium">{DEPENDENCY_LABELS[check.name] ?? check.name}</span>
                {check.critical ? null : (
                  <Badge variant="outline" className="hidden sm:inline-flex">
                    optional
                  </Badge>
                )}
                <span className="ml-auto truncate font-mono text-xs text-muted-foreground">
                  {check.status === "ok" ? `${Math.round(check.latency_ms)} ms` : check.detail}
                </span>
              </li>
            ))}
          </ul>
        ) : null}
        {!compact && data ? (
          <p className="mt-3 text-xs text-muted-foreground">
            API v{data.version} · {data.environment} · updated{" "}
            {new Date(dataUpdatedAt).toLocaleTimeString()}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
