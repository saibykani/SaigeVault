import { describe, expect, it } from "vitest";

import { nextToStart, type UploadItem } from "./upload-store";

const item = (id: string, status: UploadItem["status"]): UploadItem => ({
  id,
  name: `${id}.pdf`,
  size: 1,
  progress: 0,
  status,
});

describe("nextToStart", () => {
  it("respects the concurrency limit", () => {
    const items = [
      item("a", "uploading"),
      item("b", "uploading"),
      item("c", "queued"),
      item("d", "queued"),
    ];
    expect(nextToStart(items, 3).map((i) => i.id)).toEqual(["c"]);
  });

  it("starts nothing when the limit is reached", () => {
    const items = [item("a", "uploading"), item("b", "queued")];
    expect(nextToStart(items, 1)).toEqual([]);
  });

  it("ignores finished items", () => {
    const items = [item("a", "done"), item("b", "error"), item("c", "queued")];
    expect(nextToStart(items, 1).map((i) => i.id)).toEqual(["c"]);
  });
});
