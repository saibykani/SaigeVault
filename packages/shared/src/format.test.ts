import { describe, expect, it } from "vitest";

import { fileExtension, formatBytes, formatRelativeTime } from "./format";

describe("formatBytes", () => {
  it.each([
    [0, "0 B"],
    [1023, "1023 B"],
    [1024, "1 KB"],
    [1536, "1.5 KB"],
    [10 * 1024 * 1024, "10 MB"],
    [5.25 * 1024 ** 3, "5.3 GB"],
  ])("%d -> %s", (input, expected) => {
    expect(formatBytes(input)).toBe(expected);
  });

  it("handles invalid input", () => {
    expect(formatBytes(-1)).toBe("—");
    expect(formatBytes(Number.NaN)).toBe("—");
  });
});

describe("fileExtension", () => {
  it.each([
    ["Resume.PDF", "pdf"],
    ["archive.tar.gz", "gz"],
    ["folder/Payslip-August-2026.pdf", "pdf"],
    [".env", null],
    ["README", null],
    ["trailing.", null],
  ])("%s -> %s", (input, expected) => {
    expect(fileExtension(input)).toBe(expected);
  });
});

describe("formatRelativeTime", () => {
  const now = new Date("2026-10-01T12:00:00Z");
  it("formats past and future", () => {
    expect(formatRelativeTime(new Date("2026-09-28T12:00:00Z"), now)).toBe("3 days ago");
    expect(formatRelativeTime(new Date("2026-10-01T14:00:00Z"), now)).toBe("in 2 hours");
    expect(formatRelativeTime(new Date("2026-10-01T11:59:40Z"), now)).toBe("just now");
  });
});
