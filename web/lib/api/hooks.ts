"use client";

import { useQuery } from "@tanstack/react-query";

import { api, unwrap } from "./client";

/** Query keys in one place, so mutations (claim/unclaim) can invalidate precisely. */
export const queryKeys = {
  health: ["health"] as const,
  filters: ["filters"] as const,
};

/** Polls `/health` so the shell can show an "API unreachable" banner. */
export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: () => unwrap(api.GET("/health")),
    refetchInterval: 30_000,
    retry: false,
  });
}
