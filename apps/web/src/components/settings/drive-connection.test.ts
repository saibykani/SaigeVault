import { describe, expect, it } from "vitest";

import { driveConnectUrl } from "@/lib/api";

import { DRIVE_ERROR_MESSAGES } from "./drive-connection";

// Codes the API can place in ?drive_error= (services/api/src/saige_api/api/v1/storage.py
// and auth/google.py). Keep in sync when adding new failure modes.
const BACKEND_CODES = [
  "access_denied",
  "drive_scope_not_granted",
  "drive_offline_access_missing",
  "account_mismatch",
  "signed_out",
  "drive_not_configured",
];

describe("Drive connection", () => {
  it("has a user-facing message for every backend error code", () => {
    for (const code of BACKEND_CODES) {
      expect(DRIVE_ERROR_MESSAGES[code], code).toBeTruthy();
    }
  });

  it("builds a same-origin connect URL that returns to settings", () => {
    expect(driveConnectUrl()).toBe(
      "/api/v1/storage/google-drive/connect?next=%2Fsettings%23storage",
    );
  });
});
