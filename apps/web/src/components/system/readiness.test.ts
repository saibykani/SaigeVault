import type { ReadinessResponse } from "@saige/api-client";
import { describe, expect, it } from "vitest";

import { describeReadiness } from "./readiness";

function readiness(
  status: ReadinessResponse["status"],
  failing: { name: string; critical: boolean }[] = [],
): ReadinessResponse {
  const names = ["database", "redis", "qdrant", "worker"];
  return {
    status,
    version: "0.1.0",
    environment: "test",
    checks: names.map((name) => {
      const fail = failing.find((f) => f.name === name);
      return {
        name,
        status: fail ? "fail" : "ok",
        critical: name === "database" || name === "redis",
        latency_ms: 3,
        detail: null,
      };
    }),
  };
}

describe("describeReadiness", () => {
  it("reports an unreachable API as a failure", () => {
    expect(describeReadiness(undefined, true)).toMatchObject({
      tone: "fail",
      label: "API unreachable",
    });
  });

  it("is neutral while loading", () => {
    expect(describeReadiness(undefined, false).tone).toBe("unknown");
  });

  it("is ok when ready", () => {
    expect(describeReadiness(readiness("ready"), false).tone).toBe("ok");
  });

  it("names the failing optional dependency when degraded", () => {
    const view = describeReadiness(
      readiness("degraded", [{ name: "qdrant", critical: false }]),
      false,
    );
    expect(view.tone).toBe("warn");
    expect(view.summary).toContain("qdrant");
  });

  it("names only critical dependencies when not ready", () => {
    const view = describeReadiness(
      readiness("not_ready", [
        { name: "database", critical: true },
        { name: "worker", critical: false },
      ]),
      false,
    );
    expect(view.tone).toBe("fail");
    expect(view.summary).toContain("database");
    expect(view.summary).not.toContain("worker");
  });
});
