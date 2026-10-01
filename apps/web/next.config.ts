import type { NextConfig } from "next";

/**
 * The browser talks only to this origin. `/api/*`, `/health` and `/ready` are
 * proxied to the Saige API, so session cookies are first-party and
 * SameSite-protected (see docs/security/security-model.md).
 *
 * API_PROXY_TARGET is read at build time (e.g. http://api:8000 in Docker).
 */
const apiProxyTarget = (process.env.API_PROXY_TARGET ?? "http://localhost:8000").replace(
  /\/+$/,
  "",
);
// Optional direct API origin (only if the browser must call the API cross-origin).
const directApiUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
const isDev = process.env.NODE_ENV !== "production";
const enforceHttps = process.env.VERCEL === "1" || process.env.ENFORCE_HTTPS === "true";

/**
 * Content Security Policy.
 * - connect-src is this origin (plus an explicitly configured API origin).
 * - 'unsafe-inline' for scripts is required by Next.js hydration and the
 *   theme bootstrap script without nonces. Nonce-based CSP is tracked for the
 *   security-hardening phase.
 * - 'unsafe-eval' is only allowed in development (React Refresh).
 * - img-src allows Google profile pictures.
 */
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https://lh3.googleusercontent.com",
  "font-src 'self'",
  `connect-src 'self'${directApiUrl ? ` ${directApiUrl}` : ""}${isDev ? " ws: http://localhost:*" : ""}`,
  "frame-src 'self' blob:",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self' https://accounts.google.com",
  "frame-ancestors 'none'",
  ...(enforceHttps ? ["upgrade-insecure-requests"] : []),
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "no-referrer" },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
  ...(enforceHttps
    ? [{ key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" }]
    : []),
];

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
  transpilePackages: ["@saige/api-client", "@saige/shared", "@saige/types"],
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${apiProxyTarget}/api/:path*` },
      { source: "/health", destination: `${apiProxyTarget}/health` },
      { source: "/ready", destination: `${apiProxyTarget}/ready` },
    ];
  },
};

export default nextConfig;
