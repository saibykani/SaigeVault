import { describe, expect, it, vi } from "vitest";

import { ApiError, createApiClient } from "./index";

describe("createApiClient", () => {
  it("calls the typed endpoint and attaches a request id", async () => {
    const fetchMock = vi.fn(async (request: Request) => {
      expect(request.url).toBe("http://api.test/health");
      expect(request.headers.get("X-Request-ID")).toMatch(/^[0-9a-f]{32}$/);
      return new Response(
        JSON.stringify({ status: "ok", service: "saige-api", version: "0.1.0" }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    });
    const client = createApiClient({
      baseUrl: "http://api.test/",
      fetch: fetchMock as typeof fetch,
    });
    const { data } = await client.GET("/health");
    expect(data?.status).toBe("ok");
    expect(fetchMock).toHaveBeenCalledOnce();
  });
});

describe("ApiError", () => {
  it("parses the server error envelope", () => {
    const error = ApiError.fromResponse(404, {
      error: { code: "not_found", message: "File not found", request_id: "abc123" },
    });
    expect(error.status).toBe(404);
    expect(error.code).toBe("not_found");
    expect(error.requestId).toBe("abc123");
  });

  it("falls back gracefully for non-envelope bodies", () => {
    const error = ApiError.fromResponse(502, "Bad gateway");
    expect(error.code).toBe("http_error");
    expect(error.message).toContain("502");
  });
});
