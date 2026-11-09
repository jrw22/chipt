"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type Discipline, unwrap } from "./client";

export type SearchParams = {
  name: string;
  discipline?: Discipline;
  provider?: string;
  race?: string;
  age_group?: string;
};

/** Query keys in one place, so mutations (claim/unclaim) can invalidate precisely. */
export const queryKeys = {
  health: ["health"] as const,
  filters: ["filters"] as const,
  search: (params: SearchParams) => ["search", params] as const,
  /** Everything that depends on which results are claimed. */
  claimDependent: [["search"], ["me"], ["analysis"]] as const,
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

/** Values for the search filter dropdowns. */
export function useFilters() {
  return useQuery({
    queryKey: queryKeys.filters,
    queryFn: () => unwrap(api.GET("/filters")),
    staleTime: 5 * 60_000,
  });
}

/** Ranked candidate results; disabled until there's a name to search for. */
export function useSearch(params: SearchParams | null) {
  return useQuery({
    queryKey: queryKeys.search(params ?? { name: "" }),
    queryFn: () => unwrap(api.GET("/search", { params: { query: params! } })),
    enabled: !!params?.name,
    placeholderData: keepPreviousData,
    staleTime: 0, // claimed flags must always be fresh
  });
}

export type ClaimChanges = { claim: number[]; unclaim: number[] };
export type ClaimOutcome = { claimed: number; unclaimed: number; failed: number };

/** Apply a batch of claims/unclaims (one request each), then refresh claim-dependent views. */
export function useSaveClaims() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ claim, unclaim }: ClaimChanges): Promise<ClaimOutcome> => {
      const settled = await Promise.allSettled([
        ...claim.map((id) => unwrap(api.POST("/me/results", { body: { result_id: id } })).then(() => "claim" as const)),
        ...unclaim.map((id) =>
          unwrap(api.DELETE("/me/results/{result_id}", { params: { path: { result_id: id } } })).then(
            () => "unclaim" as const,
          ),
        ),
      ]);
      const done = settled.flatMap((s) => (s.status === "fulfilled" ? [s.value] : []));
      return {
        claimed: done.filter((d) => d === "claim").length,
        unclaimed: done.filter((d) => d === "unclaim").length,
        failed: settled.length - done.length,
      };
    },
    onSettled: () =>
      Promise.all(queryKeys.claimDependent.map((queryKey) => queryClient.invalidateQueries({ queryKey }))),
  });
}
