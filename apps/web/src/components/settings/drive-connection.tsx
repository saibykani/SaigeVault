"use client";

import type { StorageConnectionSummary } from "@saige/api-client";
import { formatBytes, formatRelativeTime } from "@saige/shared";
import { AlertTriangle, CheckCircle2, ExternalLink, FolderLock, Loader2 } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import {
  driveConnectUrl,
  useDisconnectStorage,
  useSession,
  useStorageConnections,
  useStorageQuota,
  useSystemInfo,
} from "@/lib/api";

export const DRIVE_ERROR_MESSAGES: Record<string, string> = {
  access_denied: "Google Drive access wasn't granted.",
  drive_scope_not_granted:
    "The Drive permission was unticked on Google's consent screen. Please try again and allow it.",
  drive_offline_access_missing: "Google didn't grant ongoing access. Please try connecting again.",
  account_mismatch: "Connect Drive from the same Saige account you started with.",
  signed_out: "Your session ended during connection. Sign in and try again.",
  drive_not_configured: "Google Drive isn't configured on this server.",
  invalid_state: "That connection link expired or was already used. Please try again.",
  storage_api_disabled:
    "The Google Drive API isn't enabled in this app's Google Cloud project. Enable it, then connect again.",
  storage_permission_denied: "Google Drive refused access. Please try connecting again.",
  storage_reauth_required: "Google didn't accept the Drive credentials. Please connect again.",
  storage_unavailable: "Google Drive is temporarily unavailable. Try again shortly.",
};

function GoogleDriveIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 87.3 78" aria-hidden="true" className={className}>
      <path
        fill="#0066da"
        d="m6.6 66.85 3.85 6.65c.8 1.4 1.95 2.5 3.3 3.3L27.5 53H0c0 1.55.4 3.1 1.2 4.5z"
      />
      <path
        fill="#00ac47"
        d="M43.65 25 29.9 1.2c-1.35.8-2.5 1.9-3.3 3.3L1.2 48.5A9 9 0 0 0 0 53h27.5z"
      />
      <path
        fill="#ea4335"
        d="M73.55 76.8c1.35-.8 2.5-1.9 3.3-3.3l1.6-2.75 7.65-13.25c.8-1.4 1.2-2.95 1.2-4.5H59.8l5.85 11.5z"
      />
      <path
        fill="#00832d"
        d="M43.65 25 57.4 1.2C56.05.4 54.5 0 52.9 0H34.4c-1.6 0-3.15.45-4.5 1.2z"
      />
      <path
        fill="#2684fc"
        d="M59.8 53H27.5L13.75 76.8c1.35.8 2.9 1.2 4.5 1.2h50.8c1.6 0 3.15-.45 4.5-1.2z"
      />
      <path
        fill="#ffba00"
        d="M73.4 26.5 60.7 4.5c-.8-1.4-1.95-2.5-3.3-3.3L43.65 25 59.8 53h27.45c0-1.55-.4-3.1-1.2-4.5z"
      />
    </svg>
  );
}

function QuotaBar({ connectionId }: { connectionId: string }) {
  const { data, isLoading, isError } = useStorageQuota(connectionId);
  if (isLoading) return <Skeleton className="h-8" />;
  if (isError || !data) {
    return <p className="text-xs text-muted-foreground">Storage usage is unavailable right now.</p>;
  }
  const pct = data.limit_bytes ? Math.min(100, (data.usage_bytes / data.limit_bytes) * 100) : 0;
  return (
    <div>
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>Google account storage</span>
        <span className="tabular-nums">
          {formatBytes(data.usage_bytes)}
          {data.limit_bytes ? ` of ${formatBytes(data.limit_bytes)}` : " (unlimited)"}
        </span>
      </div>
      <div
        className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-label="Google storage used"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(pct)}
      >
        <div
          className={pct > 90 ? "h-full bg-destructive" : "h-full bg-primary"}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function ConnectedDrive({ connection }: { connection: StorageConnectionSummary }) {
  const [confirming, setConfirming] = useState(false);
  const disconnect = useDisconnectStorage();
  const needsReauth = connection.status === "needs_reauth";

  return (
    <div className="space-y-3 rounded-md border p-3">
      <div className="flex items-center gap-3">
        <GoogleDriveIcon className="size-6 shrink-0" />
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-2 text-sm font-medium">
            Google Drive
            {needsReauth ? (
              <Badge variant="warning">
                <AlertTriangle />
                Reconnect needed
              </Badge>
            ) : (
              <Badge variant="success">
                <CheckCircle2 />
                Connected
              </Badge>
            )}
          </p>
          <p className="truncate text-xs text-muted-foreground">
            {connection.account_email} · connected{" "}
            {formatRelativeTime(new Date(connection.connected_at))}
          </p>
        </div>
        {needsReauth ? (
          <Button size="sm" asChild>
            <a href={driveConnectUrl()}>Reconnect</a>
          </Button>
        ) : null}
        <Button size="sm" variant="outline" onClick={() => setConfirming(true)}>
          Disconnect
        </Button>
      </div>

      {needsReauth ? (
        <p className="text-xs text-muted-foreground">
          Google no longer accepts Saige&apos;s access (it may have been revoked in your Google
          account). Reconnect to continue. Your files are safe in Drive.
        </p>
      ) : (
        <QuotaBar connectionId={connection.id} />
      )}

      <p className="flex items-start gap-2 text-xs text-muted-foreground">
        <FolderLock className="mt-px size-3.5 shrink-0" aria-hidden="true" />
        Saige can only see files it stores in its own <strong>Saige Vault</strong> folder — never
        the rest of your Drive.
      </p>

      <Dialog open={confirming} onOpenChange={setConfirming}>
        <DialogContent className="p-5">
          <DialogTitle>Disconnect Google Drive?</DialogTitle>
          <DialogDescription className="mt-2">
            Saige&apos;s access will be revoked at Google and its stored credentials deleted. Your
            files stay in your Drive, untouched. You can reconnect at any time.
          </DialogDescription>
          <div className="mt-5 flex justify-end gap-2">
            <DialogClose asChild>
              <Button variant="outline" size="sm">
                Cancel
              </Button>
            </DialogClose>
            <Button
              variant="destructive"
              size="sm"
              disabled={disconnect.isPending}
              onClick={() =>
                disconnect.mutate(connection.id, {
                  onSuccess: (result) => {
                    setConfirming(false);
                    toast.success("Google Drive disconnected", {
                      description: result.revoked_at_provider
                        ? "Access was revoked at Google."
                        : "Credentials were deleted. Google could not be reached to revoke; you can also remove access in your Google account settings.",
                    });
                  },
                  onError: () => toast.error("Couldn't disconnect Google Drive"),
                })
              }
            >
              {disconnect.isPending ? <Loader2 className="animate-spin" /> : null}
              Disconnect
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/** Shows the result of returning from Google's consent screen, then cleans the URL. */
function useDriveRedirectToast() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  useEffect(() => {
    const connected = params.get("drive") === "connected";
    const error = params.get("drive_error");
    if (!connected && !error) return;
    if (connected) toast.success("Google Drive connected");
    if (error) toast.error(DRIVE_ERROR_MESSAGES[error] ?? "Couldn't connect Google Drive.");
    router.replace(`${pathname}#storage`, { scroll: false });
  }, [params, pathname, router]);
}

export function DriveConnection() {
  useDriveRedirectToast();
  const { data: info } = useSystemInfo();
  const { data: session } = useSession();
  const { data: connections, isLoading } = useStorageConnections(Boolean(session));
  const current = connections?.find((c) => c.status !== "disconnected");

  if (!session) {
    return <p className="text-sm text-muted-foreground">Sign in to connect Google Drive.</p>;
  }
  if (isLoading) return <Skeleton className="h-28" />;
  if (current) return <ConnectedDrive connection={current} />;

  const available = info?.google_drive_available;
  return (
    <div className="flex items-center gap-3 rounded-md border p-3">
      <GoogleDriveIcon className="size-6 shrink-0" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium">Google Drive</p>
        <p className="text-xs text-muted-foreground">
          {available
            ? "Not connected. Your files will be stored in a private Saige Vault folder."
            : "Not available: the server needs Google OAuth credentials and TOKEN_ENCRYPTION_KEY."}
        </p>
      </div>
      {available ? (
        <Button size="sm" asChild>
          <a href={driveConnectUrl()}>
            Connect
            <ExternalLink />
          </a>
        </Button>
      ) : (
        <Button size="sm" disabled>
          Connect
        </Button>
      )}
    </div>
  );
}
