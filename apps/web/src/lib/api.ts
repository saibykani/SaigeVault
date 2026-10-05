"use client";

import {
  ApiError,
  createApiClient,
  createAuthFetch,
  type PasswordLoginResponse,
  type SecurityOverview,
  type SessionResponse,
  type SessionSummary,
  type SystemInfoResponse,
} from "@saige/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { env } from "@/lib/env";

/** Same-origin base URL in the browser; absolute URL needed during SSR. */
function baseUrl(): string {
  if (env.apiBaseUrl) return env.apiBaseUrl;
  return typeof window === "undefined" ? "http://localhost" : window.location.origin;
}

function redirectToLogin(): void {
  if (typeof window === "undefined" || window.location.pathname === "/login") return;
  const next = encodeURIComponent(window.location.pathname + window.location.search);
  // Full navigation (not router.push) drops every in-memory cache of vault data.
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  window.location.assign(`/login?next=${next}`);
}

export const api = createApiClient({
  baseUrl: baseUrl(),
  fetch: createAuthFetch({ baseUrl: baseUrl(), onSessionExpired: redirectToLogin }),
});

export const queryKeys = {
  systemInfo: ["system", "info"] as const,
  session: ["auth", "session"] as const,
  sessions: ["auth", "sessions"] as const,
  security: ["auth", "security"] as const,
};

async function fetchSystemInfo(): Promise<SystemInfoResponse> {
  const { data, error, response } = await api.GET("/api/v1/system/info");
  if (data) return data;
  throw ApiError.fromResponse(response.status, error);
}

/** Resolves to null when signed out (401) rather than erroring. */
async function fetchSession(): Promise<SessionResponse | null> {
  const { data, error, response } = await api.GET("/api/v1/auth/session");
  if (data) return data;
  if (response.status === 401) return null;
  throw ApiError.fromResponse(response.status, error);
}

async function fetchSessions(): Promise<SessionSummary[]> {
  const { data, error, response } = await api.GET("/api/v1/auth/sessions");
  if (data) return data.sessions;
  throw ApiError.fromResponse(response.status, error);
}

/** Free hosting sleeps when idle and takes up to ~a minute to wake. Retry for ~90 s. */
export const WAKE_RETRIES = 8;
export function wakeRetryDelay(attempt: number): number {
  return Math.min(15_000, 1_500 * 2 ** attempt);
}

export function useSystemInfo() {
  return useQuery({
    queryKey: queryKeys.systemInfo,
    queryFn: fetchSystemInfo,
    staleTime: 5 * 60_000,
    retry: WAKE_RETRIES,
    retryDelay: wakeRetryDelay,
  });
}

export function useSession() {
  return useQuery({
    queryKey: queryKeys.session,
    queryFn: fetchSession,
    staleTime: 60_000,
    retry: false,
  });
}

export function useSessions() {
  return useQuery({ queryKey: queryKeys.sessions, queryFn: fetchSessions });
}

export function useSignOut() {
  return useMutation({
    mutationFn: async () => {
      const { error, response } = await api.POST("/api/v1/auth/logout");
      if (!response.ok) throw ApiError.fromResponse(response.status, error);
    },
    onSettled: () => {
      // Full navigation clears every in-memory cache of vault data.
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.assign("/login");
    },
  });
}

export function useRevokeSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (sessionId: string) => {
      const { error, response } = await api.DELETE("/api/v1/auth/sessions/{session_id}", {
        params: { path: { session_id: sessionId } },
      });
      if (!response.ok) throw ApiError.fromResponse(response.status, error);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.sessions }),
  });
}

export function useDevLogin() {
  return useMutation({
    mutationFn: async (input: { email: string; display_name?: string }) => {
      const { data, error, response } = await api.POST("/api/v1/auth/dev-login", { body: input });
      if (!data) throw ApiError.fromResponse(response.status, error);
      return data;
    },
  });
}

// -- email + password -----------------------------------------------------------

export function useRegister() {
  return useMutation({
    mutationFn: async (input: { email: string; password: string; display_name?: string }) => {
      const { data, error, response } = await api.POST("/api/v1/auth/register", { body: input });
      if (!data) throw ApiError.fromResponse(response.status, error);
      return data;
    },
  });
}

export function usePasswordLogin() {
  return useMutation({
    mutationFn: async (input: { email: string; password: string }) => {
      const { data, error, response } = await api.POST("/api/v1/auth/login", { body: input });
      if (!data) throw ApiError.fromResponse(response.status, error);
      return data as PasswordLoginResponse;
    },
  });
}

export function useCompleteMfaLogin() {
  return useMutation({
    mutationFn: async (input: { mfa_token: string; code: string }) => {
      const { data, error, response } = await api.POST("/api/v1/auth/login/mfa", { body: input });
      if (!data) throw ApiError.fromResponse(response.status, error);
      return data as PasswordLoginResponse;
    },
  });
}

export function useSecurityOverview() {
  return useQuery({
    queryKey: queryKeys.security,
    queryFn: async (): Promise<SecurityOverview> => {
      const { data, error, response } = await api.GET("/api/v1/auth/security");
      if (data) return data;
      throw ApiError.fromResponse(response.status, error);
    },
  });
}

function useSecurityMutation<TInput, TOutput>(run: (input: TInput) => Promise<TOutput>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: run,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.security });
      void queryClient.invalidateQueries({ queryKey: queryKeys.sessions });
    },
  });
}

export function useChangePassword() {
  return useSecurityMutation(async (input: { current_password?: string; new_password: string }) => {
    const { error, response } = await api.PUT("/api/v1/auth/password", { body: input });
    if (!response.ok) throw ApiError.fromResponse(response.status, error);
  });
}

export function useTotpSetup() {
  return useMutation({
    mutationFn: async (password: string) => {
      const { data, error, response } = await api.POST("/api/v1/auth/mfa/totp/setup", {
        body: { password },
      });
      if (!data) throw ApiError.fromResponse(response.status, error);
      return data;
    },
  });
}

export function useTotpEnable() {
  return useSecurityMutation(async (code: string) => {
    const { data, error, response } = await api.POST("/api/v1/auth/mfa/totp/enable", {
      body: { code },
    });
    if (!data) throw ApiError.fromResponse(response.status, error);
    return data.recovery_codes;
  });
}

export function useTotpDisable() {
  return useSecurityMutation(async (input: { password: string; code: string }) => {
    const { error, response } = await api.POST("/api/v1/auth/mfa/totp/disable", { body: input });
    if (!response.ok) throw ApiError.fromResponse(response.status, error);
  });
}

/** True when the server can store uploads (Cloudflare R2 configured). */
export function useStorageReady(): boolean {
  const { data } = useSystemInfo();
  return data?.storage_available ?? false;
}
