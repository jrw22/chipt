"use client";

import { ArrowDown, ArrowUp, ChevronRight, CircleAlert, ListPlus, Search, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMemo } from "react";

import { EmptyState } from "@/components/empty-state";
import { AddResultDialog } from "@/components/results/add-result-dialog";
import { useUnclaimWithUndo } from "@/components/results/unclaim-with-undo";
import { TimeDisplay } from "@/components/time-display";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { ResultOut } from "@/lib/api/client";
import { useMyResults } from "@/lib/api/hooks";
import { formatDate, formatDiscipline, formatPace, ordinal, paceOf } from "@/lib/format";
import { cn } from "@/lib/utils";

/** "RaceBest", or for typed-in results "Manual entry · IRONMAN". */
function sourceLabel(r: ResultOut): string {
  return r.manual_entry && r.source_platform ? `${r.provider_name} · ${r.source_platform}` : r.provider_name;
}

type SortKey = "date" | "race" | "time";
type SortDir = "asc" | "desc";
const DEFAULT_DIR: Record<SortKey, SortDir> = { date: "desc", race: "asc", time: "asc" };

function compare(a: ResultOut, b: ResultOut, key: SortKey): number {
  if (key === "race") return a.event_name.localeCompare(b.event_name);
  if (key === "time") return a.chip_time_seconds - b.chip_time_seconds;
  return a.event_date.localeCompare(b.event_date) || a.id - b.id;
}

function SortHeader({
  label,
  sortKey,
  active,
  dir,
  onSort,
  className,
}: {
  label: string;
  sortKey: SortKey;
  active: boolean;
  dir: SortDir;
  onSort: (k: SortKey) => void;
  className?: string;
}) {
  const Icon = dir === "asc" ? ArrowUp : ArrowDown;
  const alignEnd = className?.includes("text-right"); // keep the label flush with right-aligned values
  return (
    <TableHead className={className} aria-sort={active ? (dir === "asc" ? "ascending" : "descending") : "none"}>
      <button
        type="button"
        onClick={() => onSort(sortKey)}
        className={cn(
          "inline-flex items-center gap-1 hover:text-foreground",
          alignEnd && "flex-row-reverse",
          active && "text-foreground",
        )}
      >
        {label}
        <Icon className={cn("size-3.5", active ? "opacity-100" : "opacity-0")} aria-hidden />
      </button>
    </TableHead>
  );
}

function UnclaimButton({ r }: { r: ResultOut }) {
  const { unclaim, pending } = useUnclaimWithUndo();
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="ghost"
          size="icon-sm"
          disabled={pending}
          aria-label={`Remove ${r.event_name} from your results`}
          onClick={() => unclaim(r.id, r.event_name)}
        >
          <X />
        </Button>
      </TooltipTrigger>
      <TooltipContent>Not me: remove from my results</TooltipContent>
    </Tooltip>
  );
}

function position(r: ResultOut): string {
  return r.overall_rank ? ordinal(r.overall_rank) : "–";
}

export function MyResultsView() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const discipline = searchParams.get("discipline") ?? "";
  const sortKey = (["date", "race", "time"].includes(searchParams.get("sort") ?? "")
    ? searchParams.get("sort")
    : "date") as SortKey;
  const dir = (searchParams.get("dir") === "asc" || searchParams.get("dir") === "desc"
    ? searchParams.get("dir")
    : DEFAULT_DIR[sortKey]) as SortDir;

  const setParams = (next: Record<string, string | null>) => {
    const sp = new URLSearchParams(searchParams.toString());
    for (const [k, v] of Object.entries(next)) {
      if (v) sp.set(k, v);
      else sp.delete(k);
    }
    const qs = sp.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  };
  const onSort = (k: SortKey) =>
    setParams({ sort: k, dir: k === sortKey ? (dir === "asc" ? "desc" : "asc") : DEFAULT_DIR[k] });

  const mine = useMyResults();
  const all = useMemo(() => mine.data ?? [], [mine.data]);
  const disciplines = useMemo(() => [...new Set(all.map((r) => r.discipline))].sort(), [all]);
  const rows = useMemo(() => {
    const filtered = discipline ? all.filter((r) => r.discipline === discipline) : all;
    const sign = dir === "asc" ? 1 : -1;
    return [...filtered].sort((a, b) => sign * compare(a, b, sortKey));
  }, [all, discipline, dir, sortKey]);

  if (mine.isError) {
    return (
      <Alert variant="destructive">
        <CircleAlert />
        <AlertTitle>Couldn&apos;t load your results</AlertTitle>
        <AlertDescription>{mine.error.message}</AlertDescription>
      </Alert>
    );
  }
  if (mine.isPending) {
    return (
      <div className="space-y-3" aria-busy="true" aria-label="Loading your results">
        <Skeleton className="h-8 w-64" />
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-14 w-full" />
        ))}
      </div>
    );
  }
  if (all.length === 0) {
    return (
      <EmptyState
        icon={ListPlus}
        title="No results claimed yet"
        action={
          <div className="flex flex-wrap justify-center gap-2">
            <Button asChild>
              <Link href="/find">
                <Search /> Find your results
              </Link>
            </Button>
            <AddResultDialog />
          </div>
        }
      >
        Search your name across every results provider and tick the results that are yours. They&apos;ll all
        appear here. Raced somewhere Chipt can&apos;t read, like IRONMAN? Add the result yourself.
      </EmptyState>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          <span className="font-medium text-foreground">{rows.length}</span>
          {discipline ? ` ${formatDiscipline(discipline).toLowerCase()}` : ""} result{rows.length === 1 ? "" : "s"}
          {discipline ? ` of ${all.length}` : ""}
        </p>
        <div className="flex flex-wrap items-center gap-3">
          {disciplines.length > 1 || discipline ? (
            <ToggleGroup
              type="single"
              variant="outline"
              size="sm"
              value={discipline || "all"}
              onValueChange={(v) => setParams({ discipline: v && v !== "all" ? v : null })}
              aria-label="Filter by discipline"
            >
              <ToggleGroupItem value="all">All</ToggleGroupItem>
              {(discipline && !disciplines.includes(discipline as ResultOut["discipline"])
                ? [...disciplines, discipline as ResultOut["discipline"]]
                : disciplines
              ).map((d) => (
                <ToggleGroupItem key={d} value={d}>
                  {formatDiscipline(d)}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
          ) : null}
          <AddResultDialog />
        </div>
      </div>

      {rows.length === 0 ? (
        <EmptyState
          icon={Search}
          title={`No ${formatDiscipline(discipline).toLowerCase()} results claimed`}
          action={
            <Button variant="outline" onClick={() => setParams({ discipline: null })}>
              Show all results
            </Button>
          }
        />
      ) : null}

      {/* Desktop: sortable table */}
      <Card className={cn("hidden py-0", rows.length > 0 && "md:block")}>
        <Table>
          <TableHeader>
            <TableRow>
              <SortHeader label="Date" sortKey="date" active={sortKey === "date"} dir={dir} onSort={onSort} className="pl-4" />
              <SortHeader label="Race" sortKey="race" active={sortKey === "race"} dir={dir} onSort={onSort} />
              <TableHead>Distance</TableHead>
              <SortHeader label="Time" sortKey="time" active={sortKey === "time"} dir={dir} onSort={onSort} className="text-right" />
              <TableHead className="text-right">Pace</TableHead>
              <TableHead className="text-right">Position</TableHead>
              <TableHead className="w-12 pr-4">
                <span className="sr-only">Actions</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((r) => (
              <TableRow key={r.id} className="group">
                <TableCell className="pl-4 whitespace-nowrap text-muted-foreground">{formatDate(r.event_date)}</TableCell>
                <TableCell className="max-w-72">
                  <Link href={`/results/${r.id}`} className="block truncate font-medium hover:underline">
                    {r.event_name}
                  </Link>
                  <span className="text-xs text-muted-foreground">{sourceLabel(r)}</span>
                </TableCell>
                <TableCell className="whitespace-nowrap">
                  {formatDiscipline(r.discipline)} · {r.distance_label}
                  {!r.finisher ? (
                    <Badge variant="destructive" className="ml-2">
                      DNF
                    </Badge>
                  ) : null}
                </TableCell>
                <TableCell className="text-right">
                  <TimeDisplay seconds={r.chip_time_seconds} source={r.time_source} />
                </TableCell>
                <TableCell className="text-right font-mono text-muted-foreground tabular-nums">
                  {paceOf(r) ? formatPace(paceOf(r)) : "–"}
                </TableCell>
                <TableCell className="text-right tabular-nums">{position(r)}</TableCell>
                <TableCell className="pr-4 text-right">
                  <UnclaimButton r={r} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      {/* Mobile: cards */}
      <ul className="space-y-2 md:hidden">
        {rows.map((r) => (
          <li key={r.id}>
            <Card className="flex-row items-center gap-1 py-0 pr-2">
              <Link href={`/results/${r.id}`} className="flex min-w-0 flex-1 items-center gap-3 p-4 pr-1">
                <div className="min-w-0 flex-1 space-y-1">
                  <p className="truncate font-medium">{r.event_name}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatDate(r.event_date)} · {formatDiscipline(r.discipline)} · {r.distance_label}
                  </p>
                  {r.manual_entry ? <p className="text-xs text-muted-foreground">{sourceLabel(r)}</p> : null}
                  <div className="flex items-center gap-3 text-sm">
                    <TimeDisplay seconds={r.chip_time_seconds} source={r.time_source} />
                    {r.overall_rank ? <span className="text-muted-foreground">{position(r)}</span> : null}
                    {!r.finisher ? <Badge variant="destructive">DNF</Badge> : null}
                  </div>
                </div>
                <ChevronRight className="size-4 text-muted-foreground" aria-hidden />
              </Link>
              <UnclaimButton r={r} />
            </Card>
          </li>
        ))}
      </ul>
    </div>
  );
}
