import { describe, expect, it, vi } from "vitest";

import { createAuthFetch, readCookie } from "./auth-fetch";

const BASE = "http://web.test";

function json(status: number, body: unknown = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("readCookie", () => {
  it("finds a cookie among many", () => {
    expect(readCookie("saige_csrf", "a=1; saige_csrf=abc%3D; b=2")).toBe("abc=");
    expect(readCookie("missing", "a=1")).toBeUndefined();
  });
});

describe("createAuthFetch", () => {
  it("adds the CSRF header to unsafe methods only", async () => {
    const seen: Request[] = [];
    const authFetch = createAuthFetch({
      baseUrl: BASE,
      fetch: async (r) => {
        seen.push(r as Request);
        return json(200);
      },
      getCsrfToken: () => "token-1",
    });
    await authFetch(new Request(`${BASE}/api/v1/files`));
    await authFetch(new Request(`${BASE}/api/v1/files`, { method: "POST", body: "{}" }));
    expect(seen[0]!.headers.get("X-CSRF-Token")).toBeNull();
    expect(seen[1]!.headers.get("X-CSRF-Token")).toBe("token-1");
  });

  it("refreshes once on 401 and retries with the new CSRF token", async () => {
    let csrf = "old";
    const calls: string[] = [];
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const r = input as Request;
      const path = new URL(r.url).pathname;
      calls.push(`${r.method} ${path} ${r.headers.get("X-CSRF-Token") ?? ""}`);
      if (path === "/api/v1/auth/refresh") {
        csrf = "new";
        return json(200);
      }
      return calls.filter((c) => c.includes("/api/v1/files")).length === 1 ? json(401) : json(200);
    });
    const authFetch = createAuthFetch({
      baseUrl: BASE,
      fetch: fetchMock as typeof fetch,
      getCsrfToken: () => csrf,
    });
    const response = await authFetch(
      new Request(`${BASE}/api/v1/files`, { method: "PATCH", body: '{"name":"x"}' }),
    );
    expect(response.status).toBe(200);
    expect(calls).toEqual([
      "PATCH /api/v1/files old",
      "POST /api/v1/auth/refresh old",
      "PATCH /api/v1/files new",
    ]);
  });

  it("shares one refresh between concurrent 401s", async () => {
    let refreshes = 0;
    let refreshed = false;
    const authFetch = createAuthFetch({
      baseUrl: BASE,
      fetch: (async (input: RequestInfo | URL) => {
        const path = new URL((input as Request).url).pathname;
        if (path === "/api/v1/auth/refresh") {
          refreshes += 1;
          await new Promise((r) => setTimeout(r, 10));
          refreshed = true;
          return json(200);
        }
        return refreshed ? json(200) : json(401);
      }) as typeof fetch,
      getCsrfToken: () => "t",
    });
    const results = await Promise.all([
      authFetch(new Request(`${BASE}/api/v1/a`)),
      authFetch(new Request(`${BASE}/api/v1/b`)),
    ]);
    expect(results.map((r) => r.status)).toEqual([200, 200]);
    expect(refreshes).toBe(1);
  });

  it("reports an expired session when refresh fails", async () => {
    const onSessionExpired = vi.fn();
    const authFetch = createAuthFetch({
      baseUrl: BASE,
      fetch: (async () => json(401)) as typeof fetch,
      getCsrfToken: () => "t",
      onSessionExpired,
    });
    const response = await authFetch(new Request(`${BASE}/api/v1/files`));
    expect(response.status).toBe(401);
    expect(onSessionExpired).toHaveBeenCalledOnce();
  });

  it("never retries auth endpoints", async () => {
    const fetchMock = vi.fn(async () => json(401));
    const authFetch = createAuthFetch({
      baseUrl: BASE,
      fetch: fetchMock as typeof fetch,
      getCsrfToken: () => "t",
    });
    await authFetch(new Request(`${BASE}/api/v1/auth/session`));
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it("refreshes signed-in account endpoints but not sign-in ones", async () => {
    const paths: string[] = [];
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL((input as Request).url).pathname;
      paths.push(path);
      return path === "/api/v1/auth/refresh" ? json(200) : json(401);
    });
    const authFetch = createAuthFetch({
      baseUrl: BASE,
      fetch: fetchMock as typeof fetch,
      getCsrfToken: () => "t",
    });
    await authFetch(new Request(`${BASE}/api/v1/auth/security`));
    expect(paths).toEqual([
      "/api/v1/auth/security",
      "/api/v1/auth/refresh",
      "/api/v1/auth/security",
    ]);
    paths.length = 0;
    await authFetch(new Request(`${BASE}/api/v1/auth/login`, { method: "POST", body: "{}" }));
    expect(paths).toEqual(["/api/v1/auth/login"]);
  });
});
