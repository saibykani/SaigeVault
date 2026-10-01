import type { ReadinessResponse } from "@saige/api-client";

import type { StatusTone } from "@/components/common/status-dot";

export type ReadinessView = {
  tone: StatusTone;
  label: string;
  summary: string;
};

/** Maps the API readiness payload (or a fetch failure) to UI copy. */
export function describeReadiness(
  data: ReadinessResponse | undefined,
  isError: boolean,
): ReadinessView {
  if (isError) {
    return {
      tone: "fail",
      label: "API unreachable",
      summary: "The Saige API could not be reached. Check that the backend is running.",
    };
  }
  if (!data) return { tone: "unknown", label: "Checking…", summary: "Checking system status." };
  switch (data.status) {
    case "ready":
      return {
        tone: "ok",
        label: "All systems operational",
        summary: "Every dependency is healthy.",
      };
    case "degraded": {
      const down = data.checks.filter((c) => c.status === "fail").map((c) => c.name);
      return {
        tone: "warn",
        label: "Degraded",
        summary: `Core features work; ${down.join(", ")} unavailable.`,
      };
    }
    case "not_ready": {
      const down = data.checks.filter((c) => c.status === "fail" && c.critical).map((c) => c.name);
      return {
        tone: "fail",
        label: "Unavailable",
        summary: `Critical dependency down: ${down.join(", ")}.`,
      };
    }
  }
}

export const DEPENDENCY_LABELS: Record<string, string> = {
  database: "PostgreSQL",
  redis: "Redis queue",
  qdrant: "Qdrant vector index",
  worker: "Background worker",
};
