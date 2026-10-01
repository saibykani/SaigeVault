import { Lock, ShieldCheck } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { FeatureNotice } from "@/components/common/feature-notice";
import { Logo } from "@/components/common/logo";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = { title: "Sign in" };

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

export default function LoginPage() {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center bg-surface-muted/50 px-4 py-12">
      <div className="w-full max-w-sm">
        <Link href="/" className="mx-auto mb-8 flex w-fit" aria-label="Saige Vault home">
          <Logo />
        </Link>
        <div className="rounded-xl border bg-card p-6 shadow-sm">
          <h1 className="text-lg font-semibold tracking-tight">Sign in to your vault</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Use the Google account whose Drive will hold your documents.
          </p>
          <Button variant="outline" className="mt-6 w-full" disabled>
            <GoogleIcon />
            Continue with Google
          </Button>
          <FeatureNotice featureKey="auth" className="mt-4" />
          <ul className="mt-6 space-y-2 text-[13px] text-muted-foreground">
            <li className="flex gap-2">
              <Lock className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
              OAuth tokens are stored encrypted on the server — never in your browser.
            </li>
            <li className="flex gap-2">
              <ShieldCheck className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
              Saige only accesses files you add to your vault.
            </li>
          </ul>
        </div>
      </div>
    </main>
  );
}
