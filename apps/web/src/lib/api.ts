"use client";

import {
  ApiError,
  createApiClient,
  createAuthFetch,
  type ReadinessResponse,
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
  readiness: ["system", "readiness"] as const,
  systemInfo: ["system", "info"] as const,
  session: ["auth", "session"] as const,
  sessions: ["auth", "sessions"] as const,
};

/** Readiness is meaningful even on 503, so the body is returned either way. */
async function fetchReadiness(): Promise<ReadinessResponse> {
  const { data, error, response } = await api.GET("/ready");
  if (data) return data;
  if (response.status === 503 && error) return error as ReadinessResponse;
  throw ApiError.fromResponse(response.status, error);
}

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

export function useReadiness(options?: { refetchInterval?: number }) {
  return useQuery({
    queryKey: queryKeys.readiness,
    queryFn: fetchReadiness,
    refetchInterval: options?.refetchInterval ?? 30_000,
    retry: 1,
  });
}

export function useSystemInfo() {
  return useQuery({
    queryKey: queryKeys.systemInfo,
    queryFn: fetchSystemInfo,
    staleTime: 5 * 60_000,
    retry: 1,
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
