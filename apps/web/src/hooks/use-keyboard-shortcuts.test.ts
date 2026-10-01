import { describe, expect, it } from "vitest";

import { PRIMARY_NAV, SECONDARY_NAV } from "@/lib/navigation";

import { GO_TO_SHORTCUTS, isTypingTarget } from "./use-keyboard-shortcuts";

describe("isTypingTarget", () => {
  it("detects editable elements", () => {
    expect(isTypingTarget(document.createElement("input"))).toBe(true);
    expect(isTypingTarget(document.createElement("textarea"))).toBe(true);
    const editable = document.createElement("div");
    editable.contentEditable = "true";
    // jsdom does not implement isContentEditable; emulate the browser.
    Object.defineProperty(editable, "isContentEditable", { value: true });
    expect(isTypingTarget(editable)).toBe(true);
  });

  it("ignores non-editable elements", () => {
    expect(isTypingTarget(document.createElement("button"))).toBe(false);
    expect(isTypingTarget(null)).toBe(false);
  });
});

describe("GO_TO_SHORTCUTS", () => {
  it("only targets real routes", () => {
    const routes = new Set([...PRIMARY_NAV, ...SECONDARY_NAV].map((n) => n.href));
    for (const href of Object.values(GO_TO_SHORTCUTS)) {
      expect(routes.has(href)).toBe(true);
    }
  });
});
