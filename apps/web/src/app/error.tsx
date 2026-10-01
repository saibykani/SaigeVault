"use client";

import { TriangleAlert } from "lucide-react";
import { useEffect } from "react";

import { EmptyState } from "@/components/common/empty-state";
import { Button } from "@/components/ui/button";

export default function ErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log only the digest: error messages may contain user data.
    console.error("ui_error", error.digest ?? "no-digest");
  }, [error]);

  return (
    <main className="flex min-h-[60vh] items-center justify-center">
      <EmptyState
        icon={TriangleAlert}
        title="Something went wrong"
        description={
          <>
            An unexpected error occurred.
            {error.digest ? (
              <span className="mt-1 block font-mono text-xs">Ref: {error.digest}</span>
            ) : null}
          </>
        }
      >
        <Button size="sm" onClick={reset}>
          Try again
        </Button>
      </EmptyState>
    </main>
  );
}
