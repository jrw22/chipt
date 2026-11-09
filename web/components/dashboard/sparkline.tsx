"use client";

import { Line, LineChart, YAxis } from "recharts";

import { type ChartConfig, ChartContainer } from "@/components/ui/chart";
import type { AnalysisPoint } from "@/lib/api/client";

/*
 * Stat-tile sparkline (dataviz): history in the de-emphasis hue, the latest race in the accent.
 * Decorative: the tile's own text carries every number, so it's hidden from screen readers.
 */
const config = { value: { label: "Time", color: "var(--chart-1)" } } satisfies ChartConfig;

export function Sparkline({ points }: { points: AnalysisPoint[] }) {
  if (points.length < 2) return null;
  const data = points.map((p, i) => ({ i, value: p.chip_time_seconds }));
  const last = data.length - 1;
  return (
    <ChartContainer config={config} className="aspect-auto h-10 w-full" aria-hidden>
      <LineChart data={data} margin={{ top: 6, right: 6, bottom: 6, left: 6 }}>
        <YAxis hide domain={["dataMin", "dataMax"]} />
        <Line
          dataKey="value"
          type="linear"
          stroke="var(--muted-foreground)"
          strokeOpacity={0.6}
          strokeWidth={2}
          isAnimationActive={false}
          dot={(p) =>
            p.index === last ? (
              <circle key={p.index} cx={p.cx} cy={p.cy} r={4} fill="var(--color-value)" stroke="var(--card)" strokeWidth={2} />
            ) : (
              <g key={p.index} />
            )
          }
          activeDot={false}
        />
      </LineChart>
    </ChartContainer>
  );
}
