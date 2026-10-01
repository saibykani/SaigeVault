import { type NextRequest, NextResponse } from "next/server";

/**
 * UX-level route guard: send visitors without a session hint to /login.
 *
 * This is NOT the security boundary — every API call is authorized by the
 * backend. The hint is the readable `saige_csrf` cookie, set together with the
 * HttpOnly session cookies (which are path-scoped to /api and not visible here).
 */
const SESSION_HINT_COOKIE = "saige_csrf";
const PUBLIC_PATHS = ["/login"];

export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  if (PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
    return NextResponse.next();
  }
  if (request.cookies.has(SESSION_HINT_COOKIE)) return NextResponse.next();

  const url = request.nextUrl.clone();
  url.pathname = "/login";
  url.search = pathname === "/" ? "" : `?next=${encodeURIComponent(pathname + search)}`;
  return NextResponse.redirect(url);
}

export const config = {
  // Skip API (proxied), Next internals and static assets.
  matcher: [
    "/((?!api/|health|ready|_next/|icon|apple-icon|manifest.webmanifest|icon-|favicon|.*\\.(?:png|svg|ico|webp|jpg)$).*)",
  ],
};
