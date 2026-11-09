"use client";

import { ChartLine, CircleAlert, Search } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { StatTile } from "@/components/analysis/stat-tile";
import { TimeSeriesChart } from "@/components/analysis/time-series-chart";
import { EmptyState } from "@/components/empty-state";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { latestVsPb, TREND_LABELS, trendDetail } from "@/lib/analysis";
import { ApiError, type AnalysisOut, type Discipline } from "@/lib/api/client";
import { useAnalysis } from "@/lib/api/hooks";
import { formatDate, formatDiscipline, formatDuration, formatPace } from "@/lib/format";

const groupKey = (d: string, l: string) => `${d}|${l}`;
const formatPaceAxis = (v: number) => formatPace(v).replace(" /km", "");

function AnalysisBody({ a }: { a: AnalysisOut }) {
  const n = a.points.length;
  const hasPace = a.points.some((p) => p.pace_seconds_per_km != null);
  const group = `${formatDiscipline(a.discipline).toLowerCase()} ${a.distance_label}`;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile
          label="Personal best"
          value={a.pb ? formatDuration(a.pb.chip_time_seconds) : "–"}
          detail={a.pb ? `${a.pb.event_name}, ${formatDate(a.pb.event_date)}` : undefined}
        />
        <StatTile
          label="Latest race"
          value={a.most_recent ? formatDuration(a.most_recent.chip_time_seconds) : "–"}
          detail={latestVsPb(a.most_recent_vs_pb_seconds)}
        />
        <StatTile label="Trend" value={TREND_LABELS[a.trend] ?? a.trend} detail={trendDetail(a.trend, a.trend_seconds_per_year)} />
        <StatTile
          label="Races"
          value={n}
          detail={n > 1 ? `${formatDate(a.points[0].event_date)} – ${formatDate(a.points[n - 1].event_date)}` : "Claim more to see a trend"}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Finish time</CardTitle>
          <CardDescription>Each {group} you&apos;ve finished. Lower is faster.</CardDescription>
        </CardHeader>
        <CardContent className="px-2 sm:px-4">
          <TimeSeriesChart
            points={a.points}
            field="chip_time_seconds"
            format={formatDuration}
            ariaLabel={`Finish times for ${n} ${group} races. Personal best ${a.pb ? formatDuration(a.pb.chip_time_seconds) : "none"}. Full values in the table below.`}
          />
        </CardContent>
      </Card>

      {hasPace ? (
        <Card>
          <CardHeader>
            <CardTitle>Pace</CardTitle>
            <CardDescription>Minutes per kilometre. Lower is faster.</CardDescription>
          </CardHeader>
          <CardContent className="px-2 sm:px-4">
            <TimeSeriesChart
              points={a.points}
              field="pace_seconds_per_km"
              format={formatPaceAxis}
              unit=" /km"
              ariaLabel={`Pace for ${n} ${group} races. Full values in the table below.`}
            />
          </CardContent>
        </Card>
      ) : null}

      <Card className="gap-0 py-0">
        <CardHeader className="border-b py-4">
          <CardTitle>All races</CardTitle>
        </CardHeader>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="hidden pl-4 sm:table-cell">Date</TableHead>
              <TableHead className="pl-4 sm:pl-2">Race</TableHead>
              <TableHead className="text-right">Time</TableHead>
              {hasPace ? <TableHead className="text-right">Pace</TableHead> : null}
              <TableHead className="pr-4 text-right">vs PB</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {[...a.points].reverse().map((p) => (
              <TableRow key={p.result_id}>
                <TableCell className="hidden pl-4 whitespace-nowrap text-muted-foreground sm:table-cell">
                  {formatDate(p.event_date)}
                </TableCell>
                <TableCell className="pl-4 whitespace-normal sm:max-w-64 sm:pl-2">
                  <Link href={`/results/${p.result_id}`} className="block hover:underline sm:truncate">
                    {p.event_name}
                  </Link>
                  <span className="text-xs text-muted-foreground sm:hidden">{formatDate(p.event_date)}</span>
                </TableCell>
                <TableCell className="text-right font-mono tabular-nums">{formatDuration(p.chip_time_seconds)}</TableCell>
                {hasPace ? (
                  <TableCell className="text-right font-mono text-muted-foreground tabular-nums">
                    {formatPace(p.pace_seconds_per_km)}
                  </TableCell>
                ) : null}
                <TableCell className="pr-4 text-right tabular-nums">
                  {p.is_pb ? (
                    <Badge>PB</Badge>
                  ) : (
                    <span className="font-mono text-muted-foreground">
                      +{formatDuration(p.chip_time_seconds - (a.pb?.chip_time_seconds ?? p.chip_time_seconds))}
                    </span>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}

export function AnalysisView() {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();
  const discipline = (sp.get("discipline") || undefined) as Discipline | undefined;
  const distanceLabel = sp.get("distance_label") || undefined;
  const analysis = useAnalysis({ discipline, distance_label: distanceLabel });

  const notFound = analysis.error instanceof ApiError && analysis.error.isNotFound;
  if (notFound && !discipline && !distanceLabel) {
    return (
      <EmptyState
        icon={ChartLine}
        title="Nothing to analyse yet"
        action={
          <Button asChild>
            <Link href="/find">
              <Search /> Find your results
            </Link>
          </Button>
        }
      >
        Claim your results and they&apos;ll be grouped by discipline and distance, so you only ever compare like with
        like.
      </EmptyState>
    );
  }
  if (notFound) {
    return (
      <EmptyState
        icon={ChartLine}
        title={`No ${distanceLabel ?? ""} ${discipline ? formatDiscipline(discipline).toLowerCase() : ""} results claimed`}
        action={
          <Button asChild variant="outline">
            <Link href="/analysis">Show my largest group</Link>
          </Button>
        }
      >
        Only finished races count towards analysis.
      </EmptyState>
    );
  }
  if (analysis.isError) {
    return (
      <Alert variant="destructive">
        <CircleAlert />
        <AlertTitle>Couldn&apos;t load the analysis</AlertTitle>
        <AlertDescription>{analysis.error.message}</AlertDescription>
      </Alert>
    );
  }
  if (analysis.isPending) {
    return (
      <div className="space-y-6" aria-busy="true" aria-label="Loading analysis">
        <Skeleton className="h-9 w-72" />
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
        <Skeleton className="h-80" />
      </div>
    );
  }

  const a = analysis.data;
  const current = groupKey(a.discipline, a.distance_label);
  return (
    <div className="space-y-6">
      {/* One filter row above everything it scopes. */}
      <div className="flex flex-wrap items-center gap-3">
        <Label htmlFor="group" className="text-sm text-muted-foreground">
          Comparing
        </Label>
        <Select
          value={current}
          onValueChange={(v) => {
            const [d, l] = v.split("|");
            router.replace(`${pathname}?${new URLSearchParams({ discipline: d, distance_label: l })}`, { scroll: false });
          }}
        >
          <SelectTrigger id="group" className="w-72 max-w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {(a.available_groups ?? []).map((g) => (
              <SelectItem key={groupKey(g.discipline, g.distance_label)} value={groupKey(g.discipline, g.distance_label)}>
                {formatDiscipline(g.discipline)} · {g.distance_label}
                <span className="text-muted-foreground">
                  ({g.count} race{g.count === 1 ? "" : "s"})
                </span>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      {/* Refetch keeps the frame: previous render at reduced opacity, no skeleton flash. */}
      <div className={analysis.isPlaceholderData ? "opacity-60 transition-opacity" : undefined}>
        <AnalysisBody a={a} />
      </div>
    </div>
  );
}
