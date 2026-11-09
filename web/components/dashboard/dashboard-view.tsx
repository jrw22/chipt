"use client";

import { ArrowRight, CircleAlert, Search, Trophy } from "lucide-react";
import Link from "next/link";

import { StatTile } from "@/components/analysis/stat-tile";
import { Sparkline } from "@/components/dashboard/sparkline";
import { EmptyState } from "@/components/empty-state";
import { TimeDisplay } from "@/components/time-display";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { analysisHref, latestVsPb, TREND_LABELS, trendDetail } from "@/lib/analysis";
import type { components } from "@/lib/api/schema";
import { useSummary } from "@/lib/api/hooks";
import { formatDate, formatDiscipline, formatDuration } from "@/lib/format";

type GroupSummary = components["schemas"]["GroupSummary"];

function GroupCard({ g }: { g: GroupSummary }) {
  return (
    <Link href={analysisHref(g.discipline, g.distance_label)} className="group rounded-xl focus-visible:outline-2">
      <Card className="h-full gap-3 py-4 transition-colors group-hover:border-primary/40">
        <CardHeader className="flex flex-row items-start justify-between gap-2 px-4">
          <div>
            <CardTitle className="text-sm">{g.distance_label}</CardTitle>
            <p className="text-xs text-muted-foreground">
              {formatDiscipline(g.discipline)} · {g.count} race{g.count === 1 ? "" : "s"}
            </p>
          </div>
          <ArrowRight className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" aria-hidden />
        </CardHeader>
        <CardContent className="space-y-2 px-4">
          <div>
            <p className="text-xs text-muted-foreground">Personal best</p>
            <p className="text-3xl font-semibold tracking-tight">{g.pb ? formatDuration(g.pb.chip_time_seconds) : "–"}</p>
            {g.pb ? (
              <p className="truncate text-xs text-muted-foreground">
                {g.pb.event_name}, {formatDate(g.pb.event_date)}
              </p>
            ) : null}
          </div>
          <Sparkline points={g.points} />
          <div className="space-y-0.5 border-t pt-2 text-xs">
            <p className="text-muted-foreground">{latestVsPb(g.most_recent_vs_pb_seconds)}</p>
            <p>
              <span className="font-medium">{TREND_LABELS[g.trend] ?? g.trend}</span>
              {g.trend !== "insufficient_data" ? (
                <span className="text-muted-foreground"> · {trendDetail(g.trend, g.trend_seconds_per_year)}</span>
              ) : null}
            </p>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

export function DashboardView() {
  const summary = useSummary();

  if (summary.isError) {
    return (
      <Alert variant="destructive">
        <CircleAlert />
        <AlertTitle>Couldn&apos;t load your dashboard</AlertTitle>
        <AlertDescription>{summary.error.message}</AlertDescription>
      </Alert>
    );
  }
  if (summary.isPending) {
    return (
      <div className="space-y-6" aria-busy="true" aria-label="Loading dashboard">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-56" />
          ))}
        </div>
      </div>
    );
  }

  const { totals, groups, recent } = summary.data;
  if (totals.results === 0) {
    return (
      <EmptyState
        icon={Trophy}
        title="Welcome to Chipt"
        action={
          <Button asChild>
            <Link href="/find">
              <Search /> Find your results
            </Link>
          </Button>
        }
      >
        Search your name across every results provider and claim your races. Your personal bests and trends will
        show up here.
      </EmptyState>
    );
  }

  const since = totals.first_race ? new Date(totals.first_race).getUTCFullYear() : null;
  return (
    <div className="space-y-8">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label="Results" value={totals.results} detail={`${totals.races} race${totals.races === 1 ? "" : "s"}`} />
        <StatTile label="Comparison groups" value={groups.length} detail="Same discipline and distance" />
        <StatTile label="Disciplines" value={totals.disciplines} detail={`From ${totals.providers} provider${totals.providers === 1 ? "" : "s"}`} />
        <StatTile
          label="Racing since"
          value={since ?? "–"}
          detail={totals.latest_race ? `Latest ${formatDate(totals.latest_race)}` : undefined}
        />
      </div>

      <section aria-labelledby="pbs" className="space-y-3">
        <div className="flex items-end justify-between">
          <h2 id="pbs" className="font-medium">
            Personal bests
          </h2>
          <Link href="/analysis" className="text-sm text-muted-foreground hover:text-foreground">
            Analysis →
          </Link>
        </div>
        {groups.length ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {groups.map((g) => (
              <GroupCard key={`${g.discipline}|${g.distance_label}`} g={g} />
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Your claimed results are all DNFs, so there are no personal bests yet.</p>
        )}
      </section>

      <section aria-labelledby="recent" className="space-y-3">
        <div className="flex items-end justify-between">
          <h2 id="recent" className="font-medium">
            Recent races
          </h2>
          <Link href="/results" className="text-sm text-muted-foreground hover:text-foreground">
            All results →
          </Link>
        </div>
        <Card className="gap-0 divide-y py-0">
          {recent.map((r) => (
            <Link
              key={r.id}
              href={`/results/${r.id}`}
              className="flex items-center gap-4 px-4 py-3 transition-colors first:rounded-t-xl last:rounded-b-xl hover:bg-muted/50"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{r.event_name}</p>
                <p className="text-xs text-muted-foreground">
                  {formatDate(r.event_date)} · {formatDiscipline(r.discipline)} · {r.distance_label}
                </p>
              </div>
              {!r.finisher ? <Badge variant="destructive">DNF</Badge> : null}
              <TimeDisplay seconds={r.chip_time_seconds} source={r.time_source} className="text-sm" />
            </Link>
          ))}
        </Card>
      </section>
    </div>
  );
}
