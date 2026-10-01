import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { LoginPanel } from "@/components/auth/login-panel";
import { Logo } from "@/components/common/logo";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = { title: "Sign in" };

export default function LoginPage() {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center bg-surface-muted/50 px-4 py-12">
      <div className="w-full max-w-sm">
        <Link href="/" className="mx-auto mb-8 flex w-fit" aria-label="Saige Vault home">
          <Logo />
        </Link>
        <Suspense fallback={<Skeleton className="h-80 rounded-xl" />}>
          <LoginPanel />
        </Suspense>
      </div>
    </main>
  );
}
