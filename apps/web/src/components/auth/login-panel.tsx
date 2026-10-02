"use client";

import { FlaskConical, Loader2, Lock, ShieldCheck } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useDevLogin, useSystemInfo } from "@/lib/api";

const ERROR_MESSAGES: Record<string, string> = {
  access_denied: "Sign-in was cancelled.",
  invalid_state: "That sign-in link expired or was already used. Please try again.",
  google_not_configured: "Google sign-in isn't configured on this server yet.",
  email_not_verified: "Your Google account email isn't verified.",
  nonce_mismatch: "Sign-in could not be verified. Please try again.",
  forbidden: "This account is disabled.",
  rate_limited: "Too many attempts. Please wait a minute and try again.",
};

/** Only same-site relative paths, mirroring the server's open-redirect guard. */
export function safeNext(candidate: string | null): string {
  if (!candidate || !candidate.startsWith("/") || candidate.startsWith("//")) return "/";
  if (candidate.includes("\\")) return "/";
  return candidate;
}

function GoogleIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="size-4">
      <path
        fill="#4285F4"
        d="M22.6 12.2c0-.8-.1-1.5-.2-2.2H12v4.2h6a5.1 5.1 0 0 1-2.2 3.4v2.8h3.6c2.1-1.9 3.2-4.8 3.2-8.2Z"
      />
      <path
        fill="#34A853"
        d="M12 23c3 0 5.5-1 7.4-2.7l-3.6-2.8c-1 .7-2.3 1.1-3.8 1.1-2.9 0-5.4-2-6.3-4.6H2v2.9A11 11 0 0 0 12 23Z"
      />
      <path
        fill="#FBBC05"
        d="M5.7 14c-.2-.7-.4-1.4-.4-2s.2-1.4.4-2V7.1H2A11 11 0 0 0 1 12c0 1.8.4 3.4 1.1 4.9L5.7 14Z"
      />
      <path
        fill="#EA4335"
        d="M12 5.4c1.6 0 3.1.6 4.3 1.7l3.2-3.2A11 11 0 0 0 2 7.1L5.7 10C6.6 7.3 9.1 5.4 12 5.4Z"
      />
    </svg>
  );
}

export function LoginPanel() {
  const params = useSearchParams();
  const next = safeNext(params.get("next"));
  const errorCode = params.get("error");
  const { data: info, isLoading, isError, failureCount, refetch } = useSystemInfo();
  const devLogin = useDevLogin();
  const [email, setEmail] = useState("");

  const googleHref = `/api/v1/auth/google/login?next=${encodeURIComponent(next)}`;

  async function onDevLogin(event: FormEvent) {
    event.preventDefault();
    await devLogin.mutateAsync({ email: email.trim() });
    window.location.assign(next);
  }

  return (
    <div className="rounded-xl border bg-card p-6 shadow-sm">
      <h1 className="text-lg font-semibold tracking-tight">Sign in to your vault</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Use the Google account whose Drive will hold your documents.
      </p>

      {errorCode ? (
        <p
          role="alert"
          className="mt-4 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          {ERROR_MESSAGES[errorCode] ?? "Sign-in failed. Please try again."}
        </p>
      ) : null}

      {isLoading && failureCount > 0 ? (
        <div
          role="status"
          className="mt-6 flex items-start gap-2.5 rounded-md bg-muted px-3 py-2.5 text-sm"
        >
          <Loader2 className="mt-0.5 size-4 shrink-0 animate-spin text-muted-foreground" />
          <span className="text-muted-foreground">
            Waking up the server… This can take up to a minute after it has been idle.
          </span>
        </div>
      ) : isLoading ? (
        <Skeleton className="mt-6 h-9" />
      ) : isError ? (
        <div role="alert" className="mt-6 text-sm">
          <p className="text-destructive">
            The Saige server didn&apos;t respond, so sign-in isn&apos;t available right now.
          </p>
          <Button variant="outline" size="sm" className="mt-3" onClick={() => void refetch()}>
            Try again
          </Button>
        </div>
      ) : info?.google_oauth_configured ? (
        <Button asChild variant="outline" className="mt-6 w-full">
          <a href={googleHref}>
            <GoogleIcon />
            Continue with Google
          </a>
        </Button>
      ) : (
        <>
          <Button variant="outline" className="mt-6 w-full" disabled>
            <GoogleIcon />
            Continue with Google
          </Button>
          <p className="mt-2 text-xs text-muted-foreground">
            Google sign-in isn&apos;t configured on this server. Set GOOGLE_CLIENT_ID,
            GOOGLE_CLIENT_SECRET and GOOGLE_REDIRECT_URI.
          </p>
        </>
      )}

      {info?.dev_login_enabled ? (
        <form onSubmit={onDevLogin} className="mt-6 border-t pt-5">
          <p className="mb-2 flex items-center gap-1.5 text-xs font-medium text-warning">
            <FlaskConical className="size-3.5" aria-hidden="true" />
            Development sign-in (disabled in production)
          </p>
          <label htmlFor="dev-email" className="sr-only">
            Email
          </label>
          <div className="flex gap-2">
            <Input
              id="dev-email"
              type="email"
              required
              autoComplete="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <Button type="submit" disabled={devLogin.isPending}>
              {devLogin.isPending ? <Loader2 className="animate-spin" /> : null}
              Sign in
            </Button>
          </div>
          {devLogin.isError ? (
            <p role="alert" className="mt-2 text-xs text-destructive">
              {devLogin.error.message}
            </p>
          ) : null}
        </form>
      ) : null}

      <ul className="mt-6 space-y-2 text-[13px] text-muted-foreground">
        <li className="flex gap-2">
          <Lock className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          Session tokens live in secure, HttpOnly cookies — never readable by scripts.
        </li>
        <li className="flex gap-2">
          <ShieldCheck className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          Sign-in only asks Google for your name and email. Drive access is a separate, explicit
          step.
        </li>
      </ul>
    </div>
  );
}
