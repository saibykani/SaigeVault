import { describe, expect, it } from "vitest";

import { WAKE_RETRIES, wakeRetryDelay } from "./api";

describe("cold-start retry policy", () => {
  it("keeps retrying long enough for a sleeping free-tier server to wake", () => {
    const total = Array.from({ length: WAKE_RETRIES }, (_, i) => wakeRetryDelay(i)).reduce(
      (a, b) => a + b,
      0,
    );
    expect(total).toBeGreaterThanOrEqual(60_000);
    expect(total).toBeLessThanOrEqual(120_000);
  });

  it("caps individual delays", () => {
    expect(wakeRetryDelay(20)).toBe(15_000);
  });
});
