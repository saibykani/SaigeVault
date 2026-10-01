/**
 * Public (browser-visible) configuration. Only NEXT_PUBLIC_* values belong
 * here — never secrets.
 *
 * By default the browser calls the API on this same origin (proxied by
 * Next.js), which keeps session cookies first-party.
 */
export const env = {
  apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL ?? "",
} as const;
