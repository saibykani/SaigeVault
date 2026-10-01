import { describe, expect, it } from "vitest";

import { describeUserAgent } from "@/components/settings/sessions-list";
import { initials } from "@/components/shell/account-menu";

import { safeNext } from "./login-panel";

describe("safeNext", () => {
  it.each([
    [null, "/"],
    ["/files", "/files"],
    ["/search?q=salary", "/search?q=salary"],
    ["https://evil.example", "/"],
    ["//evil.example", "/"],
    ["/\\evil.example", "/"],
  ])("%s -> %s", (input, expected) => {
    expect(safeNext(input)).toBe(expected);
  });
});

describe("initials", () => {
  it("uses the display name when present", () => {
    expect(initials("Sai Bykani", "x@example.com")).toBe("SB");
  });
  it("falls back to the email local part", () => {
    expect(initials(null, "krishna.bykani@example.com")).toBe("KB");
    expect(initials("", "alice@example.com")).toBe("AL");
  });
});

describe("describeUserAgent", () => {
  it.each([
    [
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0 Safari/537.36",
      "Chrome on Windows",
    ],
    [
      "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1",
      "Safari on iOS",
    ],
    [null, "Unknown device"],
  ])("%s", (ua, expected) => {
    expect(describeUserAgent(ua)).toBe(expected);
  });
});
