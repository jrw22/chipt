"use client";

import { ExternalLink } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { ClaimBar } from "@/components/find/claim-bar";
import { TimeDisplay } from "@/components/time-display";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import type { SearchResultOut } from "@/lib/api/client";
import { useSaveClaims } from "@/lib/api/hooks";
import { formatDate, formatDiscipline } from "@/lib/format";
import { cn } from "@/lib/utils";

type EventGroup = {
  eventId: number;
  sample: SearchResultOut;
  results: SearchResultOut[];
  bestScore: number;
};

/** Group candidates by event: events ordered by their best match, rows by score within an event. */
function groupByEvent(results: SearchResultOut[]): EventGroup[] {
  const groups = new Map<number, EventGroup>();
  for (const r of results) {
    const g = groups.get(r.event_id) ?? { eventId: r.event_id, sample: r, results: [], bestScore: 0 };
    g.results.push(r);
    g.bestScore = Math.max(g.bestScore, r.score);
    groups.set(r.event_id, g);
  }
  return [...groups.values()].sort(
    (a, b) => b.bestScore - a.bestScore || b.sample.event_date.localeCompare(a.sample.event_date),
  );
}

function ordinal(n: number): string {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return `${n}${s[(v - 20) % 10] || s[v] || s[0]}`;
}

function MatchBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  return (
    // Deliberately quiet: a surname-only search scores everyone 100%, so loud badges would be noise.
    <Badge variant="secondary" className="font-normal text-muted-foreground tabular-nums" title="How closely this name matches your search">
      {pct}% match
    </Badge>
  );
}

export function SearchResults({ results, limitReached }: { results: SearchResultOut[]; limitReached: boolean }) {
  // Desired "mine" state per result id, only for rows the user has toggled.
  const [desired, setDesired] = useState<Map<number, boolean>>(new Map());
  const save = useSaveClaims();
  const groups = useMemo(() => groupByEvent(results), [results]);

  const isMine = (r: SearchResultOut) => desired.get(r.id) ?? r.claimed;
  const pending = useMemo(() => {
    const claim: number[] = [];
    const unclaim: number[] = [];
    for (const r of results) {
      const want = desired.get(r.id);
      if (want === undefined || want === r.claimed) continue;
      (want ? claim : unclaim).push(r.id);
    }
    return { claim, unclaim };
  }, [desired, results]);

  const toggle = (r: SearchResultOut, checked: boolean) =>
    setDesired((prev) => {
      const next = new Map(prev);
      if (checked === r.claimed) next.delete(r.id);
      else next.set(r.id, checked);
      return next;
    });

  const onSave = () =>
    save.mutate(pending, {
      onSuccess: ({ claimed, unclaimed, failed }) => {
        const parts = [
          claimed && `Claimed ${claimed} result${claimed === 1 ? "" : "s"}`,
          unclaimed && `removed ${unclaimed}`,
        ].filter(Boolean);
        if (parts.length) {
          const msg = parts.join(", ");
          toast.success(msg.charAt(0).toUpperCase() + msg.slice(1) + ".");
        }
        if (failed) toast.error(`${failed} change${failed === 1 ? "" : "s"} failed. Please try again.`);
        setDesired(new Map());
      },
    });

  const raceCount = groups.length;
  return (
    <div className="space-y-4 pb-24">
      <p className="text-sm text-muted-foreground">
        <span className="font-medium text-foreground">{results.length}</span> possible result
        {results.length === 1 ? "" : "s"} across {raceCount} race{raceCount === 1 ? "" : "s"}, best match first. Tick
        the ones that are yours.
        {limitReached ? " Showing the closest matches only: add a filter to narrow it down." : null}
      </p>

      {groups.map((g) => {
        const e = g.sample;
        return (
          <Card key={g.eventId} className="gap-0 py-0">
            <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-x-4 gap-y-1 border-b py-3">
              <div className="min-w-0">
                <h2 className="truncate font-medium">{e.event_name}</h2>
                <p className="text-sm text-muted-foreground">
                  {formatDate(e.event_date)} · {formatDiscipline(e.discipline)} · {e.distance_label}
                </p>
              </div>
              <a
                href={e.source_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
              >
                {e.provider_name}
                <ExternalLink className="size-3" />
              </a>
            </CardHeader>
            <CardContent className="divide-y px-0">
              {g.results.map((r) => {
                const mine = isMine(r);
                const changed = desired.has(r.id);
                const id = `mine-${r.id}`;
                return (
                  <label
                    key={r.id}
                    htmlFor={id}
                    className={cn(
                      "grid cursor-pointer grid-cols-[auto_1fr_auto] items-center gap-x-3 gap-y-1 px-4 py-3 transition-colors hover:bg-muted/50 sm:grid-cols-[auto_1fr_auto_auto]",
                      mine && "bg-primary/5",
                      changed && "ring-1 ring-primary/40 ring-inset",
                    )}
                  >
                    <Checkbox
                      id={id}
                      checked={mine}
                      onCheckedChange={(c) => toggle(r, c === true)}
                      aria-label={`This is me: ${r.athlete_name}, ${e.event_name}`}
                    />
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="truncate font-medium">{r.athlete_name}</span>
                        {r.claimed && !changed ? <Badge variant="outline">Yours</Badge> : null}
                        {!r.finisher ? <Badge variant="destructive">DNF</Badge> : null}
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {[
                          r.age_group,
                          r.gender,
                          r.overall_rank ? `${ordinal(r.overall_rank)} overall` : null,
                        ]
                          .filter(Boolean)
                          .join(" · ") || "No category details"}
                      </p>
                    </div>
                    <TimeDisplay
                      seconds={r.chip_time_seconds}
                      source={r.time_source}
                      className="justify-self-end text-sm"
                    />
                    <div className="col-start-2 sm:col-start-auto sm:justify-self-end">
                      <MatchBadge score={r.score} />
                    </div>
                  </label>
                );
              })}
            </CardContent>
          </Card>
        );
      })}

      <ClaimBar
        claimCount={pending.claim.length}
        unclaimCount={pending.unclaim.length}
        saving={save.isPending}
        onSave={onSave}
        onDiscard={() => setDesired(new Map())}
      />
    </div>
  );
}
