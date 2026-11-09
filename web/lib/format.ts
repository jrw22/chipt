/** Display formatting shared by every page (ported from the Streamlit UI's fmt_* helpers). */

/** 2710 -> "45:10", 3723 -> "1:02:03". Sign is dropped; use `formatSigned` for deltas. */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || Number.isNaN(seconds)) return "–";
  const s = Math.round(Math.abs(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const mm = String(m).padStart(h ? 2 : 1, "0");
  const ss = String(sec).padStart(2, "0");
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

/** Delta vs a reference: "+1:05" slower, "-0:42" faster, "±0:00" equal. */
export function formatSigned(seconds: number | null | undefined): string {
  if (seconds == null || Number.isNaN(seconds)) return "–";
  const sign = seconds > 0 ? "+" : seconds < 0 ? "−" : "±";
  return `${sign}${formatDuration(seconds)}`;
}

/** Seconds per km -> "4:35 /km". */
export function formatPace(secondsPerKm: number | null | undefined): string {
  if (secondsPerKm == null || Number.isNaN(secondsPerKm)) return "–";
  const total = Math.round(secondsPerKm);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")} /km`;
}

/** Seconds per km for single-discipline results (distance_km is null for multi-sport). */
export function paceOf(r: { chip_time_seconds: number; distance_km?: number | null }): number | null {
  return r.distance_km ? r.chip_time_seconds / r.distance_km : null;
}

/** 1 -> "1st", 22 -> "22nd", 113 -> "113th". */
export function ordinal(n: number): string {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return `${n}${s[(v - 20) % 10] || s[v] || s[0]}`;
}

/** Position as a share of the field, rounded up: 12 of 154 -> "Top 8%"; 1st -> "Winner". */
export function topPercent(rank: number, of: number): string {
  if (rank === 1) return "Winner";
  return `Top ${Math.max(1, Math.ceil((rank / of) * 100))}%`;
}

/** ISO date ("2025-06-01") -> "1 Jun 2025", without timezone drift. */
export function formatDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

const DISCIPLINE_LABELS: Record<string, string> = {
  running: "Running",
  cycling: "Cycling",
  swimming: "Swimming",
  triathlon: "Triathlon",
  duathlon: "Duathlon",
};

export function formatDiscipline(d: string): string {
  return DISCIPLINE_LABELS[d] ?? d;
}
