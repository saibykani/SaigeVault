/**
 * fetch wrapper for cookie-authenticated browser clients.
 *
 * - Adds the double-submit CSRF header (read from the `saige_csrf` cookie at
 *   send time) to unsafe methods.
 * - On 401 from a non-auth endpoint, performs one token refresh and retries the
 *   original request once. Concurrent 401s share a single refresh.
 */

export const CSRF_COOKIE = "saige_csrf";
export const CSRF_HEADER = "X-CSRF-Token";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);
const AUTH_PATH = "/api/v1/auth/";
const REFRESH_PATH = "/api/v1/auth/refresh";

export interface AuthFetchOptions {
  baseUrl: string;
  fetch?: typeof fetch;
  /** Returns the current CSRF cookie value. Injectable for tests. */
  getCsrfToken?: () => string | undefined;
  /** Called when the session cannot be refreshed (user must sign in again). */
  onSessionExpired?: () => void;
}

export function readCookie(name: string, cookieString: string): string | undefined {
  for (const part of cookieString.split(";")) {
    const [key, ...rest] = part.trim().split("=");
    if (key === name) return decodeURIComponent(rest.join("="));
  }
  return undefined;
}

function browserCsrfToken(): string | undefined {
  return typeof document === "undefined" ? undefined : readCookie(CSRF_COOKIE, document.cookie);
}

export function createAuthFetch({
  baseUrl,
  fetch: baseFetch = globalThis.fetch.bind(globalThis),
  getCsrfToken = browserCsrfToken,
  onSessionExpired,
}: AuthFetchOptions): (request: Request) => Promise<Response> {
  let refreshing: Promise<boolean> | null = null;

  function withCsrf(request: Request): Request {
    if (SAFE_METHODS.has(request.method.toUpperCase())) return request;
    const token = getCsrfToken();
    if (!token) return request;
    const headers = new Headers(request.headers);
    headers.set(CSRF_HEADER, token);
    return new Request(request, { headers });
  }

  async function refresh(): Promise<boolean> {
    const url = `${baseUrl.replace(/\/+$/, "")}${REFRESH_PATH}`;
    const response = await baseFetch(
      withCsrf(new Request(url, { method: "POST", credentials: "include" })),
    );
    return response.ok;
  }

  function refreshOnce(): Promise<boolean> {
    refreshing ??= refresh()
      .catch(() => false)
      .finally(() => {
        refreshing = null;
      });
    return refreshing;
  }

  return async function authFetch(request: Request): Promise<Response> {
    const retry = request.clone();
    const response = await baseFetch(withCsrf(request));
    const isAuthCall = new URL(request.url, "http://local").pathname.startsWith(AUTH_PATH);
    if (response.status !== 401 || isAuthCall) return response;

    if (await refreshOnce()) return baseFetch(withCsrf(retry));
    onSessionExpired?.();
    return response;
  };
}
