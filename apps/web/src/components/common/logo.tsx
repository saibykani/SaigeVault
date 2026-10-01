import { cn } from "@/lib/utils";

/** Saige Vault mark: a vault outline enclosing a sage leaf. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      aria-hidden="true"
      className={cn("size-7 shrink-0", className)}
      fill="none"
    >
      <rect x="2" y="2" width="28" height="28" rx="8" className="fill-primary" />
      <path
        d="M10 21.5c0-6.5 4.7-11 12-11.5-.4 7.3-5 12-11.5 12H10v-.5Z"
        className="fill-primary-foreground"
        opacity="0.95"
      />
      <path
        d="M10.5 21.5 17 15"
        className="stroke-primary"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function Logo({
  className,
  collapsed = false,
}: {
  className?: string;
  collapsed?: boolean;
}) {
  return (
    <span className={cn("flex items-center gap-2.5", className)}>
      <LogoMark />
      {collapsed ? null : (
        <span className="text-[15px] font-semibold tracking-tight">
          Saige <span className="text-muted-foreground">Vault</span>
        </span>
      )}
    </span>
  );
}
