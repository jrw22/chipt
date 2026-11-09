"use client";

import { ArrowLeft, ChartLine, Check, CircleAlert, ExternalLink, Plus, SearchX } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

import { EmptyState } from "@/components/empty-state";
import { useUnclaimWithUndo } from "@/components/results/unclaim-with-undo";
import { TimeDisplay } from "@/components/time-display";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, type ResultDetailOut } from "@/lib/api/client";
import { useResult, useSetClaimed } from "@/lib/api/hooks";
import { formatDate, formatDiscipline, formatPace, ordinal, paceOf, topPercent } from "@/lib/format";

function PositionCard({ label, rank, of, note }: { label: string; rank?: number | null; of?: number | null; note?: string }) {
  return (
    <Card className="gap-1 py-4">
      <CardHeader className="px-4">
        <CardTitle className="text-xs font-normal text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-0.5 px-4">
        {rank ? (
          <>
            <p className="text-2xl font-semibold tabular-nums">
              {ordinal(rank)}
              {of ? <span className="text-base font-normal text-muted-foreground"> of {of}</span> : null}
            </p>
            <p className="text-xs text-muted-foreground">
              {[of ? topPercent(rank, of) : null, note].filter(Boolean).join(" · ") || " "}
            </p>
          </>
        ) : (
          <p className="text-2xl font-semibold text-muted-foreground">–</p>
        )}
      </CardContent>
    </Card>
  );
}

function ClaimToggle({ r }: { r: ResultDetailOut }) {
  const setClaimed = useSetClaimed();
  const { unclaim, pending } = useUnclaimWithUndo();
  if (r.claimed) {
    return (
      <Button variant="outline" disabled={pending} onClick={() => unclaim(r.id, r.event_name)}>
        <Check /> Yours · Remove
      </Button>
    );
  }
  return (
    <Button
      disabled={setClaimed.isPending}
      onClick={() =>
        setClaimed.mutate(
          { id: r.id, claimed: true },
          {
            onSuccess: () => toast.success("Added to your results."),
            onError: (e) => toast.error(`Couldn't claim it: ${e.message}`),
          },
        )
      }
    >
      <Plus /> This is me
    </Button>
  );
}

export function ResultDetailView({ id }: { id: number }) {
  const result = useResult(id);
  const validId = Number.isInteger(id) && id > 0;

  if (!validId || (result.error instanceof ApiError && result.error.isNotFound)) {
    return (
      <EmptyState
        icon={SearchX}
        title="Result not found"
        action={
          <Button asChild variant="outline">
            <Link href="/results">Back to my results</Link>
          </Button>
        }
      >
        It may have been removed when its race was re-ingested.
      </EmptyState>
    );
  }
  if (result.isPending) {
    return (
      <div className="space-y-6" aria-busy="true" aria-label="Loading result">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-24 w-full" />
        <div className="grid gap-3 sm:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      </div>
    );
  }
  if (result.isError) {
    return (
      <Alert variant="destructive">
        <CircleAlert />
        <AlertTitle>Couldn&apos;t load this result</AlertTitle>
        <AlertDescription>{result.error.message}</AlertDescription>
      </Alert>
    );
  }

  const r = result.data;
  const pace = paceOf(r);
  const analysisHref = `/analysis?${new URLSearchParams({ discipline: r.discipline, distance_label: r.distance_label })}`;

  return (
    <div className="space-y-6">
      <Button asChild variant="ghost" size="sm" className="-ml-2 text-muted-foreground">
        <Link href="/results">
          <ArrowLeft /> My results
        </Link>
      </Button>

      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">{r.event_name}</h1>
          <p className="text-sm text-muted-foreground">
            {formatDate(r.event_date)} · {formatDiscipline(r.discipline)} · {r.distance_label}
            {r.location ? ` · ${r.location}` : ""}
          </p>
          <p className="text-sm">
            {r.athlete_name}
            <span className="text-muted-foreground">{[r.age_group, r.gender].filter(Boolean).map((x) => ` · ${x}`)}</span>
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <ClaimToggle r={r} />
          {r.claimed && r.finisher ? (
            <Button asChild variant="outline">
              <Link href={analysisHref}>
                <ChartLine /> Compare
              </Link>
            </Button>
          ) : null}
        </div>
      </div>

      <Card className="py-5">
        <CardContent className="flex flex-wrap items-end gap-x-10 gap-y-4 px-5">
          <div>
            <p className="text-xs text-muted-foreground">{r.time_source === "chip" ? "Chip time" : "Finish time"}</p>
            <TimeDisplay seconds={r.chip_time_seconds} source={r.time_source} className="text-4xl font-semibold" />
          </div>
          {pace ? (
            <div>
              <p className="text-xs text-muted-foreground">Pace</p>
              <p className="font-mono text-xl tabular-nums">{formatPace(pace)}</p>
            </div>
          ) : null}
          {!r.finisher ? (
            <Badge variant="destructive" className="mb-1">
              Did not finish
            </Badge>
          ) : null}
        </CardContent>
      </Card>

      {r.finisher ? (
        <section aria-labelledby="positions" className="space-y-3">
          <h2 id="positions" className="text-sm font-medium">
            Positions
          </h2>
          <div className="grid gap-3 sm:grid-cols-3">
            <PositionCard label="Overall" rank={r.overall_rank} of={r.event_finishers} />
            <PositionCard label={r.gender ? `Gender (${r.gender})` : "Gender"} rank={r.gender_rank} of={r.gender_finishers} />
            <PositionCard
              label={r.age_group ? `Category (${r.age_group})` : "Category"}
              rank={r.category_rank}
              of={r.category_finishers}
            />
          </div>
          <p className="text-xs text-muted-foreground">
            Field sizes count finishers in this event as published by {r.provider_name}.
          </p>
        </section>
      ) : null}

      <a
        href={r.source_url}
        target="_blank"
        rel="noreferrer"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        View on {r.provider_name} <ExternalLink className="size-3.5" />
      </a>
    </div>
  );
}
