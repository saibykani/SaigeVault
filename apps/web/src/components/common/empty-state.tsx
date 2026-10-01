import type { LucideIcon } from "lucide-react";
import type * as React from "react";

import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  children,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn("flex flex-col items-center justify-center px-6 py-14 text-center", className)}
    >
      <div className="mb-4 flex size-11 items-center justify-center rounded-xl border bg-surface-muted">
        <Icon className="size-5 text-muted-foreground" aria-hidden="true" />
      </div>
      <h2 className="text-[15px] font-semibold">{title}</h2>
      <div className="mt-1.5 max-w-md text-sm text-muted-foreground">{description}</div>
      {children ? <div className="mt-5 flex flex-wrap justify-center gap-2">{children}</div> : null}
    </div>
  );
}
