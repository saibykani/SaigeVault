"use client";

import { formatRelativeTime } from "@saige/shared";
import { Check, Copy, KeyRound, Loader2, ShieldCheck } from "lucide-react";
import { type FormEvent, useMemo, useState } from "react";
import { toast } from "sonner";
import { encode } from "uqr";

import { PasswordField } from "@/components/auth/password-form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useChangePassword,
  useSecurityOverview,
  useTotpDisable,
  useTotpEnable,
  useTotpSetup,
} from "@/lib/api";

function ErrorLine({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <p role="alert" className="text-xs text-destructive">
      {error instanceof Error ? error.message : "Something went wrong. Please try again."}
    </p>
  );
}

/** QR code drawn as SVG rects (no innerHTML, no network). */
export function QrCode({ value, label }: { value: string; label: string }) {
  const { data, size } = useMemo(() => encode(value, { border: 2 }), [value]);
  const path = useMemo(() => {
    let d = "";
    data.forEach((row, y) =>
      row.forEach((dark, x) => {
        if (dark) d += `M${x} ${y}h1v1h-1z`;
      }),
    );
    return d;
  }, [data]);
  return (
    <svg
      viewBox={`0 0 ${size} ${size}`}
      role="img"
      aria-label={label}
      className="size-44 rounded-md bg-white"
      shapeRendering="crispEdges"
    >
      <path d={path} fill="#000" />
    </svg>
  );
}

function PasswordDialog({
  open,
  onOpenChange,
  hasPassword,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  hasPassword: boolean;
}) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const change = useChangePassword();

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    await change.mutateAsync({
      new_password: next,
      ...(hasPassword ? { current_password: current } : {}),
    });
    toast.success(
      hasPassword ? "Password changed. Your other devices were signed out." : "Password added.",
    );
    setCurrent("");
    setNext("");
    onOpenChange(false);
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        change.reset();
        onOpenChange(value);
      }}
    >
      <DialogContent className="p-5">
        <DialogTitle>{hasPassword ? "Change password" : "Add a password"}</DialogTitle>
        <DialogDescription className="mt-1">
          {hasPassword
            ? "You'll stay signed in here. Every other device will be signed out."
            : "Then you can also sign in with your email and password."}
        </DialogDescription>
        <form onSubmit={(e) => void onSubmit(e).catch(() => undefined)} className="mt-4 space-y-3">
          {hasPassword ? (
            <PasswordField
              id="current-password"
              label="Current password"
              value={current}
              onChange={setCurrent}
              autoComplete="current-password"
            />
          ) : null}
          <PasswordField
            id="new-password"
            label="New password"
            value={next}
            onChange={setNext}
            autoComplete="new-password"
          />
          <p className="text-xs text-muted-foreground">
            Passwords found in known data breaches are refused.
          </p>
          <ErrorLine error={change.error} />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={change.isPending}>
              {change.isPending ? <Loader2 className="animate-spin" /> : null}
              Save password
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function RecoveryCodes({ codes, onDone }: { codes: string[]; onDone: () => void }) {
  const [copied, setCopied] = useState(false);
  const text = codes.join("\n");
  return (
    <div className="mt-4 space-y-3">
      <p className="text-sm">
        Save these recovery codes somewhere safe, like a password manager. Each one signs you in
        once if you lose your phone. <strong>They won&apos;t be shown again.</strong>
      </p>
      <ul className="grid grid-cols-2 gap-1.5 rounded-md border bg-muted/40 p-3 font-mono text-sm">
        {codes.map((c) => (
          <li key={c}>{c}</li>
        ))}
      </ul>
      <div className="flex justify-end gap-2">
        <Button
          variant="outline"
          onClick={() => {
            void navigator.clipboard.writeText(text).then(() => setCopied(true));
          }}
        >
          {copied ? <Check /> : <Copy />}
          {copied ? "Copied" : "Copy codes"}
        </Button>
        <Button onClick={onDone}>I&apos;ve saved them</Button>
      </div>
    </div>
  );
}

function EnableTotpDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [recovery, setRecovery] = useState<string[] | null>(null);
  const setup = useTotpSetup();
  const enable = useTotpEnable();

  function close() {
    setPassword("");
    setCode("");
    setRecovery(null);
    setup.reset();
    enable.reset();
    onOpenChange(false);
  }

  return (
    <Dialog open={open} onOpenChange={(value) => (value ? onOpenChange(true) : close())}>
      <DialogContent className="p-5" onInteractOutside={(e) => e.preventDefault()}>
        <DialogTitle>Turn on two-step verification</DialogTitle>
        {recovery ? (
          <RecoveryCodes codes={recovery} onDone={close} />
        ) : setup.data ? (
          <form
            className="mt-4 space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              void enable
                .mutateAsync(code.trim())
                .then((codes) => {
                  setRecovery(codes);
                  toast.success("Two-step verification is on.");
                })
                .catch(() => setCode(""));
            }}
          >
            <DialogDescription>
              Scan this with an authenticator app (Google Authenticator, Microsoft Authenticator,
              1Password…), then enter the 6-digit code it shows.
            </DialogDescription>
            <div className="flex justify-center">
              <QrCode value={setup.data.otpauth_uri} label="Authenticator setup QR code" />
            </div>
            <p className="text-center text-xs text-muted-foreground">
              Can&apos;t scan? Enter this key:{" "}
              <code className="font-mono break-all text-foreground">{setup.data.secret}</code>
            </p>
            <label htmlFor="totp-code" className="sr-only">
              6-digit code
            </label>
            <Input
              id="totp-code"
              required
              autoFocus
              inputMode="numeric"
              autoComplete="one-time-code"
              placeholder="123456"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
            />
            <ErrorLine error={enable.error} />
            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={close}>
                Cancel
              </Button>
              <Button type="submit" disabled={enable.isPending || code.length !== 6}>
                {enable.isPending ? <Loader2 className="animate-spin" /> : null}
                Turn on
              </Button>
            </div>
          </form>
        ) : (
          <form
            className="mt-4 space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              void setup.mutateAsync(password).catch(() => undefined);
            }}
          >
            <DialogDescription>
              After this, signing in with your password will also need a code from your phone.
              Confirm your password to continue.
            </DialogDescription>
            <PasswordField
              id="totp-password"
              label="Password"
              value={password}
              onChange={setPassword}
              autoComplete="current-password"
            />
            <ErrorLine error={setup.error} />
            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={close}>
                Cancel
              </Button>
              <Button type="submit" disabled={setup.isPending || !password}>
                {setup.isPending ? <Loader2 className="animate-spin" /> : null}
                Continue
              </Button>
            </div>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

function DisableTotpDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const disable = useTotpDisable();

  function close() {
    setPassword("");
    setCode("");
    disable.reset();
    onOpenChange(false);
  }

  return (
    <Dialog open={open} onOpenChange={(value) => (value ? onOpenChange(true) : close())}>
      <DialogContent className="p-5">
        <DialogTitle>Turn off two-step verification</DialogTitle>
        <DialogDescription className="mt-1">
          Your account will be protected by your password alone.
        </DialogDescription>
        <form
          className="mt-4 space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            void disable
              .mutateAsync({ password, code: code.trim() })
              .then(() => {
                toast.success("Two-step verification is off.");
                close();
              })
              .catch(() => undefined);
          }}
        >
          <PasswordField
            id="disable-password"
            label="Password"
            value={password}
            onChange={setPassword}
            autoComplete="current-password"
          />
          <div>
            <label htmlFor="disable-code" className="mb-1 block text-xs font-medium">
              Authenticator or recovery code
            </label>
            <Input
              id="disable-code"
              required
              autoComplete="one-time-code"
              maxLength={32}
              value={code}
              onChange={(e) => setCode(e.target.value)}
            />
          </div>
          <ErrorLine error={disable.error} />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={close}>
              Cancel
            </Button>
            <Button
              type="submit"
              variant="destructive"
              disabled={disable.isPending || !password || code.trim().length < 6}
            >
              {disable.isPending ? <Loader2 className="animate-spin" /> : null}
              Turn off
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function AccountSecurity() {
  const { data, isLoading, isError } = useSecurityOverview();
  const [dialog, setDialog] = useState<"password" | "enable" | "disable" | null>(null);

  if (isLoading) return <Skeleton className="h-28" />;
  if (isError || !data) {
    return <p className="text-sm text-muted-foreground">Security settings are unavailable.</p>;
  }

  const canAddPassword = data.has_password || data.email_verified;
  return (
    <div className="divide-y rounded-md border">
      <div className="flex items-center gap-3 px-3 py-3 text-sm">
        <KeyRound className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <p className="font-medium">Password</p>
          <p className="text-xs text-muted-foreground">
            {data.has_password
              ? data.password_changed_at
                ? `Last changed ${formatRelativeTime(new Date(data.password_changed_at))}`
                : "Set"
              : canAddPassword
                ? "Not set. You sign in with Google."
                : "Sign in with Google once to verify your email, then you can add a password."}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          disabled={!canAddPassword}
          onClick={() => setDialog("password")}
        >
          {data.has_password ? "Change" : "Add password"}
        </Button>
      </div>

      <div className="flex items-center gap-3 px-3 py-3 text-sm">
        <ShieldCheck className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-2 font-medium">
            Two-step verification
            {data.totp_enabled ? <Badge variant="success">On</Badge> : <Badge>Off</Badge>}
          </p>
          <p className="text-xs text-muted-foreground">
            {data.totp_enabled
              ? `Password sign-in also needs a code from your authenticator app. ${data.recovery_codes_remaining} recovery codes left.`
              : data.has_password
                ? "Add a code from your phone to password sign-in."
                : "Available once you add a password. Google sign-in uses your Google account's own security."}
          </p>
        </div>
        {data.totp_enabled ? (
          <Button variant="outline" size="sm" onClick={() => setDialog("disable")}>
            Turn off
          </Button>
        ) : (
          <Button size="sm" disabled={!data.has_password} onClick={() => setDialog("enable")}>
            Turn on
          </Button>
        )}
      </div>

      <PasswordDialog
        open={dialog === "password"}
        onOpenChange={(open) => setDialog(open ? "password" : null)}
        hasPassword={data.has_password}
      />
      <EnableTotpDialog
        open={dialog === "enable"}
        onOpenChange={(open) => setDialog(open ? "enable" : null)}
      />
      <DisableTotpDialog
        open={dialog === "disable"}
        onOpenChange={(open) => setDialog(open ? "disable" : null)}
      />
    </div>
  );
}
