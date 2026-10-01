import { FileQuestion } from "lucide-react";
import Link from "next/link";

import { EmptyState } from "@/components/common/empty-state";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <main className="flex min-h-dvh items-center justify-center">
      <EmptyState
        icon={FileQuestion}
        title="Page not found"
        description="This page doesn't exist, or you don't have access to it."
      >
        <Button asChild size="sm">
          <Link href="/">Back to dashboard</Link>
        </Button>
      </EmptyState>
    </main>
  );
}
