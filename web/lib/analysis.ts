/** Wording for analysis numbers, shared by the Analysis page and the Dashboard. */
import { formatDuration, formatSigned } from "@/lib/format";

export type Trend = "improving" | "declining" | "flat" | "insufficient_data" | string;

export const TREND_LABELS: Record<string, string> = {
  improving: "Improving",
  declining: "Slowing",
  flat: "Steady",
  insufficient_data: "Not enough races",
};

/** "1:05 faster per year" from a linear-fit slope (negative seconds = getting faster). */
export function trendDetail(trend: Trend, slope: number | null | undefined): string {
  if (trend === "insufficient_data" || slope == null) return "Needs races on 2+ dates";
  if (Math.abs(slope) < 1) return "About the same each year";
  return `${formatDuration(slope)} ${slope < 0 ? "faster" : "slower"} per year`;
}

/** "PB!" when the latest race is the PB, otherwise "+1:05 vs PB". */
export function latestVsPb(deltaSeconds: number | null | undefined): string {
  if (deltaSeconds == null) return "–";
  if (deltaSeconds === 0) return "Your latest race is your PB";
  return `${formatSigned(deltaSeconds)} vs PB`;
}

/** URL for the Analysis page of one comparison group. */
export function analysisHref(discipline: string, distanceLabel: string): string {
  return `/analysis?${new URLSearchParams({ discipline, distance_label: distanceLabel })}`;
}
