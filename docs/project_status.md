# Project status

## Current milestone
**V1** (see `project_spec.md` §3 and the [V1 plan](v1_plan.md)). The MVP is complete; PRs #1 and #2 are merged.

Phase 1 is the Next.js UI, replacing Streamlit.

## Done
- [x] Project scaffold: uv project, Docker Postgres (port 5433), `.env` settings
- [x] Canonical schema (Pydantic + SQL), idempotent upserts, `pg_trgm` index, seeded single athlete
- [x] Shared scraper interface, polite HTTP client, normalisation helpers, ingest CLI
- [x] **Search** by name (fuzzy) + discipline / provider / race / age group, and **claim** results
- [x] **Initial analysis**: time series of chip times within a `(discipline, distance_label)` group
- [x] Streamlit UI (Find & Claim, My Results, Analysis), checked end to end against the real API
- [x] Backend API: search, claims and analysis, tested end to end on real data
- [x] **Ingest ≥2 races from ≥2 providers.** RaceBest (12 events, 3,876 results) and UKResults (7 events, 2,537 results). Re-running is idempotent.
- [x] Event Chip Timing (RaceTec, user-run): ATW Grafman 2025 + 2026, triathlon and aquabike
- [x] **MVP complete** (2026-11-09)
- [x] V1 plan agreed: [docs/v1_plan.md](v1_plan.md)

## In progress
- V1 phase 1, step 1: `feature/v1-web-scaffold` (Next.js + Tailwind + shadcn/ui shell, generated API client)

## Next up
- V1 phase 1, steps 2–5: Find & Claim → My results + detail → Analysis + dashboard → Playwright smoke tests, then retire Streamlit
- V1 phases 2–5: API feeds, more providers and races, advanced analysis, better search
- RunThrough: the owner runs the scraper by hand (`list` → pin RIds → `dump` → ingest)

## Blockers / open questions
- **resultsbase.net** is blocked by Cloudflare Turnstile. Next step: ask info@resultsbase.net for access or a feed.
- **RunThrough** has opted out of AI agents. The owner runs the scraper, and its data stays out of LLM features. Asking for a feed is still the cleanest route.
- **Event Chip Timing** has the same AI-agent opt-out as RunThrough (both are RaceTec sites), so the same rules apply. Still unverified: whether the `StartPage.aspx` listing exists on this site. The site publishes gun time only, with no chip time.
- **UKResults** publishes no terms. Get explicit permission before V2 or public use.
- On this Mac the venv's editable `.pth` keeps getting the hidden flag, which breaks `uv run chipt-*` imports. The workarounds are in the README; root cause unknown.
- Holmfirth 10K 2023 uses different age categories and has no gender column, so its age groups don't line up with later years.
