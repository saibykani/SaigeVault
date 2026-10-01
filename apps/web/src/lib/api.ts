"use client";

import {
  ApiError,
  createApiClient,
  type ReadinessResponse,
  type SystemInfoResponse,
} from "@saige/api-client";
import { useQuery } from "@tanstack/react-query";

import { env } from "@/lib/env";

export const api = createApiClient({ baseUrl: env.apiBaseUrl });

export const queryKeys = {
  readiness: ["system", "readiness"] as const,
  systemInfo: ["system", "info"] as const,
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
