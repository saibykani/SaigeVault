import { Construction } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { type FeatureKey, feature } from "@/lib/features";
import { cn } from "@/lib/utils";

export function PhaseBadge({
  featureKey,
  className,
}: {
  featureKey: FeatureKey;
  className?: string;
}) {
  const f = feature(featureKey);
  if (f.available) return null;
  return (
    <Badge
      variant="outline"
      className={cn("font-mono", className)}
      title={`${f.label} ships in Phase ${f.phase}`}
    >
      P{f.phase}
    </Badge>
  );
}

/**
 * Inline notice explaining that a capability is not yet built. Renders
 * nothing once the feature is marked available.
 */
export function FeatureNotice({
  featureKey,
  className,
}: {
  featureKey: FeatureKey;
  className?: string;
}) {
  const f = feature(featureKey);
  if (f.available) return null;
  return (
    <div
      role="note"
      className={cn(
        "flex items-start gap-3 rounded-lg border border-dashed bg-surface-muted/60 px-4 py-3 text-sm",
        className,
      )}
    >
      <Construction className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      <p className="text-muted-foreground">
        <span className="font-medium text-foreground">{f.label}</span> arrives in{" "}
        <span className="font-medium text-foreground">Phase {f.phase}</span>. {f.description}
      </p>
    </div>
  );
}
