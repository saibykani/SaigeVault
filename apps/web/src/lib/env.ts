/**
 * Public (browser-visible) configuration. Only NEXT_PUBLIC_* values belong
 * here — never secrets.
 */
export const env = {
  apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000",
} as const;
