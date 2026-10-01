import createClient, { type Client, type Middleware } from "openapi-fetch";

import type { components, paths } from "./schema.gen";

export type { components, paths };
export type Schemas = components["schemas"];
export type ReadinessResponse = Schemas["ReadinessResponse"];
export type SystemInfoResponse = Schemas["SystemInfoResponse"];
export type ErrorResponse = Schemas["ErrorResponse"];

export type SaigeApiClient = Client<paths>;

export interface ApiClientOptions {
  baseUrl: string;
  /** Inject a fetch implementation (tests, SSR). */
  fetch?: typeof fetch;
}

/** Error thrown for non-2xx responses, carrying the server's error envelope. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId: string | null;

  constructor(status: number, code: string, message: string, requestId: string | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }

  static fromResponse(status: number, body: unknown): ApiError {
    const envelope = (body as Partial<ErrorResponse> | undefined)?.error;
    return new ApiError(
      status,
      envelope?.code ?? "http_error",
      envelope?.message ?? `Request failed with status ${status}`,
      envelope?.request_id ?? null,
    );
  }
}

const requestIdMiddleware: Middleware = {
  onRequest({ request }) {
    if (!request.headers.has("X-Request-ID") && typeof crypto !== "undefined") {
      request.headers.set("X-Request-ID", crypto.randomUUID().replaceAll("-", ""));
    }
    return request;
  },
};

export function createApiClient({ baseUrl, fetch: fetchImpl }: ApiClientOptions): SaigeApiClient {
  const client = createClient<paths>({
    baseUrl: baseUrl.replace(/\/+$/, ""),
    // Session cookies (Phase 3) are HttpOnly and sent automatically.
    credentials: "include",
    ...(fetchImpl ? { fetch: fetchImpl } : {}),
  });
  client.use(requestIdMiddleware);
  return client;
}
