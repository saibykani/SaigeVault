import { cn } from "@/lib/utils";

export type StatusTone = "ok" | "warn" | "fail" | "unknown";

const TONE_CLASS: Record<StatusTone, string> = {
  ok: "bg-success",
  warn: "bg-warning",
  fail: "bg-destructive",
  unknown: "bg-muted-foreground/40",
};

export function StatusDot({ tone, className }: { tone: StatusTone; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn("inline-block size-2 shrink-0 rounded-full", TONE_CLASS[tone], className)}
    />
  );
}
