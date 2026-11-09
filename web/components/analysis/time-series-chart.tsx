"use client";

import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";

import { type ChartConfig, ChartContainer, ChartTooltip } from "@/components/ui/chart";
import type { AnalysisPoint } from "@/lib/api/client";
import { formatDate } from "@/lib/format";

/*
 * One series over time (dataviz rules): 2px accent line, 8px dots with a 2px surface ring,
 * no legend (the card title names the series), direct labels only on the PB and the latest
 * race, recessive solid hairline grid, crosshair + value-first tooltip. The table under the
 * chart carries every value, so the tooltip never gates anything.
 */

const DAY = 86_400_000;
const config = { value: { label: "Time", color: "var(--chart-1)" } } satisfies ChartConfig;

type Datum = { t: number; value: number; point: AnalysisPoint };

function toTime(iso: string): number {
  const [y, m, d] = iso.split("-").map(Number);
  return Date.UTC(y, m - 1, d);
}

/** Yearly ticks for long spans, quarterly-ish month ticks for short ones. */
function timeTicks(min: number, max: number): { ticks: number[]; format: (t: number) => string } {
  const span = max - min;
  if (span > 540 * DAY) {
    const ticks: number[] = [];
    for (let y = new Date(min).getUTCFullYear(); y <= new Date(max).getUTCFullYear() + 1; y++) {
      const t = Date.UTC(y, 0, 1);
      if (t >= min && t <= max) ticks.push(t);
    }
    return { ticks, format: (t) => String(new Date(t).getUTCFullYear()) };
  }
  return {
    ticks: [],
    format: (t) => new Date(t).toLocaleDateString("en-GB", { month: "short", year: "numeric", timeZone: "UTC" }),
  };
}

/** Round time steps (seconds), so axis ticks land on clean values like 1:20:00 or 7:30. */
const TIME_STEPS = [5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200];

/** ~4–6 ticks on a round step that covers [min, max], plus the matching domain. */
function niceTimeTicks(min: number, max: number): { ticks: number[]; domain: [number, number] } {
  const range = Math.max(max - min, 1);
  const step = TIME_STEPS.find((s) => range / s <= 5) ?? TIME_STEPS[TIME_STEPS.length - 1];
  let lo = Math.floor(min / step) * step;
  let hi = Math.ceil(max / step) * step;
  if (lo === hi) {
    lo -= step;
    hi += step;
  }
  if (min - lo < step * 0.15) lo -= step; // breathing room so dots never sit on the edge
  if (hi - max < step * 0.15) hi += step;
  lo = Math.max(0, lo);
  const ticks: number[] = [];
  for (let v = lo; v <= hi + 1e-9; v += step) ticks.push(v);
  return { ticks, domain: [lo, hi] };
}

function PointDot(props: {
  cx?: number;
  cy?: number;
  payload?: Datum;
  index?: number;
  lastIndex: number;
  format: (v: number) => string;
}) {
  const { cx, cy, payload, index, lastIndex, format } = props;
  if (cx == null || cy == null || !payload) return null;
  const isPb = payload.point.is_pb;
  const isLast = index === lastIndex;
  const label = isPb && isLast ? `PB · ${format(payload.value)}` : isPb ? `PB ${format(payload.value)}` : isLast ? format(payload.value) : null;
  return (
    <g>
      <circle cx={cx} cy={cy} r={isPb ? 6 : 4} fill="var(--color-value)" stroke="var(--card)" strokeWidth={2} />
      {label ? (
        <text
          x={cx}
          y={cy - 12}
          textAnchor={isLast && lastIndex > 0 ? "end" : "middle"}
          className="fill-foreground text-[11px] font-medium"
        >
          {label}
        </text>
      ) : null}
    </g>
  );
}

function TooltipBody({
  active,
  payload,
  format,
  unit,
}: {
  active?: boolean;
  payload?: { payload: Datum }[];
  format: (v: number) => string;
  unit: string;
}) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="grid min-w-40 gap-1 rounded-lg border bg-popover px-3 py-2 text-xs shadow-md">
      <div className="flex items-center gap-2">
        <span className="h-0.5 w-3 rounded-full bg-(--color-value)" aria-hidden />
        <span className="text-sm font-semibold text-foreground">
          {format(d.value)}
          {unit}
        </span>
        {d.point.is_pb ? <span className="font-medium text-muted-foreground">PB</span> : null}
      </div>
      <p className="text-muted-foreground">{d.point.event_name}</p>
      <p className="text-muted-foreground">{formatDate(d.point.event_date)}</p>
    </div>
  );
}

export function TimeSeriesChart({
  points,
  field,
  format,
  unit = "",
  ariaLabel,
}: {
  points: AnalysisPoint[];
  field: "chip_time_seconds" | "pace_seconds_per_km";
  format: (v: number) => string;
  unit?: string;
  ariaLabel: string;
}) {
  const data: Datum[] = points
    .filter((p) => p[field] != null)
    .map((p) => ({ t: toTime(p.event_date), value: p[field] as number, point: p }));
  if (data.length === 0) return null;

  const tMin = data[0].t;
  const tMax = data[data.length - 1].t;
  const pad = Math.max((tMax - tMin) * 0.06, 60 * DAY); // keep end labels off the plot edge
  const domainX: [number, number] = [tMin - pad, tMax + pad];
  const { ticks, format: tickFormat } = timeTicks(domainX[0], domainX[1]);
  const values = data.map((d) => d.value);
  const y = niceTimeTicks(Math.min(...values), Math.max(...values));

  return (
    <ChartContainer config={config} className="aspect-auto h-64 w-full sm:h-72" role="img" aria-label={ariaLabel}>
      <LineChart data={data} margin={{ top: 24, right: 16, bottom: 0, left: 4 }} accessibilityLayer>
        <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="0" />
        <XAxis
          dataKey="t"
          type="number"
          scale="time"
          domain={domainX}
          ticks={ticks.length ? ticks : undefined}
          tickFormatter={tickFormat}
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          minTickGap={24}
          className="tabular-nums"
        />
        <YAxis
          dataKey="value"
          domain={y.domain}
          ticks={y.ticks}
          tickFormatter={(v: number) => format(v)}
          tickLine={false}
          axisLine={false}
          width={56}
          className="tabular-nums"
        />
        <ChartTooltip
          cursor={{ stroke: "var(--muted-foreground)", strokeWidth: 1 }}
          content={<TooltipBody format={format} unit={unit} />}
        />
        <Line
          dataKey="value"
          type="linear"
          stroke="var(--color-value)"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
          isAnimationActive={false}
          dot={(p) => <PointDot key={p.index} {...p} lastIndex={data.length - 1} format={format} />}
          activeDot={{ r: 6, fill: "var(--color-value)", stroke: "var(--card)", strokeWidth: 2 }}
        />
      </LineChart>
    </ChartContainer>
  );
}
