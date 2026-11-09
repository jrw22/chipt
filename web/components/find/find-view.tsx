"use client";

import { CircleAlert, SearchX, Trophy } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMemo } from "react";

import { SearchForm } from "@/components/find/search-form";
import { SearchResults } from "@/components/find/search-results";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { Discipline } from "@/lib/api/client";
import { type SearchParams, useFilters, useSearch } from "@/lib/api/hooks";

const SEARCH_LIMIT = 50; // the API's default (SEARCH_MAX_RESULTS)
const KEYS = ["discipline", "provider", "race", "age_group"] as const;

function paramsFromUrl(sp: URLSearchParams): SearchParams | null {
  const name = sp.get("name")?.trim();
  if (!name) return null;
  const out: SearchParams = { name };
  for (const k of KEYS) {
    const v = sp.get(k)?.trim();
    if (v) (out as Record<string, string>)[k] = v;
  }
  if (out.discipline) out.discipline = out.discipline as Discipline;
  return out;
}

function urlFromParams(params: SearchParams): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v) sp.set(k, v);
  return sp.toString();
}

function EmptyCard({ icon: Icon, title, children }: { icon: typeof Trophy; title: string; children: React.ReactNode }) {
  return (
    <Card className="border-dashed">
      <CardContent className="flex flex-col items-center gap-2 py-12 text-center">
        <Icon className="size-8 text-muted-foreground" aria-hidden />
        <h2 className="font-medium">{title}</h2>
        <div className="max-w-md text-sm text-muted-foreground">{children}</div>
      </CardContent>
    </Card>
  );
}

function ResultsSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Loading results">
      {[0, 1].map((i) => (
        <Card key={i} className="gap-3 p-4">
          <Skeleton className="h-5 w-1/3" />
          <Skeleton className="h-4 w-1/4" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </Card>
      ))}
    </div>
  );
}

export function FindView() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const queryString = searchParams.toString();
  const params = useMemo(() => paramsFromUrl(new URLSearchParams(queryString)), [queryString]);
  const search = useSearch(params);
  const filters = useFilters();

  return (
    <div className="space-y-8">
      {/* key: re-seed the form's fields when the URL changes (back/forward). */}
      <SearchForm
        key={queryString}
        initial={params}
        onSearch={(p) => router.push(`${pathname}?${urlFromParams(p)}`, { scroll: false })}
      />

      {!params ? (
        <EmptyCard icon={Trophy} title="Find your race results">
          Search your name to see results from{" "}
          {filters.data ? `${filters.data.providers.length} results providers` : "every results provider"} in one
          place, then tick the ones that are yours.
        </EmptyCard>
      ) : search.isError ? (
        <Alert variant="destructive">
          <CircleAlert />
          <AlertTitle>Search failed</AlertTitle>
          <AlertDescription>{search.error.message}</AlertDescription>
        </Alert>
      ) : search.isPending ? (
        <ResultsSkeleton />
      ) : search.data.length === 0 ? (
        <EmptyCard icon={SearchX} title={`No results for “${params.name}”`}>
          Try a different spelling, just your surname, or fewer filters.
        </EmptyCard>
      ) : (
        <div className={search.isPlaceholderData ? "opacity-60 transition-opacity" : undefined}>
          {/* key: a new search starts with no unsaved ticks. */}
          <SearchResults
            key={queryString}
            results={search.data}
            limitReached={search.data.length >= SEARCH_LIMIT}
          />
        </div>
      )}
    </div>
  );
}
