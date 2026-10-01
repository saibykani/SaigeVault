"use client";

import { formatRelativeTime } from "@saige/shared";
import { Laptop, Smartphone } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useRevokeSession, useSessions, useSignOut } from "@/lib/api";

/** Short, human description of a user agent. Display only. */
export function describeUserAgent(ua: string | null | undefined): string {
  if (!ua) return "Unknown device";
  const browser = /Edg\//.test(ua)
    ? "Edge"
    : /Firefox\//.test(ua)
      ? "Firefox"
      : /Chrome\//.test(ua)
        ? "Chrome"
        : /Safari\//.test(ua)
          ? "Safari"
          : "Browser";
  const os = /iPhone|iPad/.test(ua)
    ? "iOS"
    : /Android/.test(ua)
      ? "Android"
      : /Mac OS X/.test(ua)
        ? "macOS"
        : /Windows/.test(ua)
          ? "Windows"
          : /Linux/.test(ua)
            ? "Linux"
            : "";
  return os ? `${browser} on ${os}` : browser;
}

export function SessionsList() {
  const { data: sessions, isLoading, isError } = useSessions();
  const revoke = useRevokeSession();
  const signOut = useSignOut();

  if (isLoading) return <Skeleton className="h-24" />;
  if (isError || !sessions) {
    return <p className="text-sm text-muted-foreground">Sign in to manage your sessions.</p>;
  }

  return (
    <ul className="divide-y rounded-md border">
      {sessions.map((s) => {
        const mobile = /iPhone|iPad|Android/.test(s.user_agent ?? "");
        const Icon = mobile ? Smartphone : Laptop;
        return (
          <li key={s.id} className="flex items-center gap-3 px-3 py-2.5 text-sm">
            <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            <div className="min-w-0 flex-1">
              <p className="flex items-center gap-2 font-medium">
                <span className="truncate">{describeUserAgent(s.user_agent)}</span>
                {s.current ? <Badge variant="success">This device</Badge> : null}
              </p>
              <p className="truncate text-xs text-muted-foreground">
                Signed in {formatRelativeTime(new Date(s.started_at))}
                {s.last_seen_at ? ` · active ${formatRelativeTime(new Date(s.last_seen_at))}` : ""}
                {s.ip_address ? ` · ${s.ip_address}` : ""}
              </p>
            </div>
            {s.current ? (
              <Button size="sm" variant="outline" onClick={() => signOut.mutate()}>
                Sign out
              </Button>
            ) : (
              <Button
                size="sm"
                variant="outline"
                disabled={revoke.isPending}
                onClick={() =>
                  revoke.mutate(s.id, {
                    onSuccess: () => toast.success("Session signed out"),
                    onError: () => toast.error("Couldn't sign out that session"),
                  })
                }
              >
                Revoke
              </Button>
            )}
          </li>
        );
      })}
    </ul>
  );
}
