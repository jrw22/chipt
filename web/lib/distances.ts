import type { Discipline } from "@/lib/api/client";

/**
 * Canonical distance labels per discipline for the "Add a result" form. They mirror the labels
 * the scrapers produce (`_RUN_DISTANCES` / `_MULTI_DISTANCES` in `src/chipt/ingest/normalise.py`),
 * so a typed-in result lands in the same comparison group as scraped ones.
 */
export const DISTANCE_LABELS: Record<Discipline, string[]> = {
  running: ["5K", "5 Mile", "10K", "10 Mile", "Half Marathon", "Marathon", "Ultra"],
  triathlon: ["Super Sprint", "Sprint", "Sprint Plus", "Olympic", "Middle Distance (70.3)", "Full Distance (140.6)"],
  duathlon: ["Sprint", "Olympic", "Middle Distance"],
  cycling: [],
  swimming: [],
};

export const DISCIPLINES: Discipline[] = ["running", "triathlon", "duathlon", "cycling", "swimming"];
