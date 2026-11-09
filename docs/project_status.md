# Project status

## Current milestone
**V1** (see `project_spec.md` §3 and the [V1 plan](v1_plan.md)). The MVP is complete; PRs #1 and #2 are merged.

**Phase 1 (Next.js UI) is complete:** Streamlit is retired, and the new UI is covered by `npm run check` and a Playwright smoke test. Phases 2–5 are next (see the plan).

## Done
- [x] Project scaffold: uv project, Docker Postgres (port 5433), `.env` settings
- [x] Canonical schema (Pydantic + SQL), idempotent upserts, `pg_trgm` index, seeded single athlete
- [x] Shared scraper interface, polite HTTP client, normalisation helpers, ingest CLI
- [x] **Search** by name (fuzzy) + discipline / provider / race / age group, and **claim** results
- [x] **Initial analysis**: time series of chip times within a `(discipline, distance_label)` group
- [x] Streamlit UI (Find & Claim, My Results, Analysis), checked end to end against the real API (MVP; replaced by Next.js in V1)
- [x] Backend API: search, claims and analysis, tested end to end on real data
- [x] **Ingest ≥2 races from ≥2 providers.** RaceBest (12 events, 3,876 results) and UKResults (7 events, 2,537 results). Re-running is idempotent.
- [x] Event Chip Timing (RaceTec, user-run): ATW Grafman 2025 + 2026, triathlon and aquabike
- [x] **MVP complete** (2026-11-09)
- [x] V1 plan agreed: [docs/v1_plan.md](v1_plan.md)
- [x] V1 phase 1 step 1: Next.js scaffold (PR #3)
- [x] V1 phase 1 step 2: Find & Claim page + `time_source` (PR #4)
- [x] V1 phase 1 step 3: My results + result detail (PR #5)
- [x] V1 phase 1 step 4: Analysis + Dashboard + `/me/summary` (PR #6)
- [x] **V1 phase 1 complete:** Playwright smoke test, Streamlit retired (PR #7)

## In progress
- V1 phase 2, step 1 on `feature/v1-platform-review`: UK results-platform review (`docs/providers/platform_review.md`) with access routes. **Waiting for the owner to approve the route-1 shortlist** (Eventrac, race-results.co.uk)

## Next up
- **IRONMAN API spike** (next, owner-paced): the owner signs up at the IRONMAN API Portal and checks the API terms. Then the agent builds the first `api` provider on the user-run pattern (see `docs/providers/ironman.md`)
- V1 phase 2, step 2: manual-import route (`chipt-import`) + British Triathlon parser. **Owner action:** save the Belvoir results page into `imports/britishtriathlon/`
- V1 phase 2, steps 3–4: Eventrac and race-results.co.uk scrapers; more RaceBest/UKResults races
- Later: API feeds (deferred), advanced analysis, better search
- RunThrough: the owner runs the scraper by hand (`list` → pin RIds → `dump` → ingest)

## Blockers / open questions
- **resultsbase.net** is blocked by Cloudflare Turnstile and now also opts out `ClaudeBot`/`GPTBot`. Route: manual import, or ask for access.
- **British Triathlon** (the owner's priority for triathlon) is behind Cloudflare on every page. Route: manual import (phase 2 step 2); ask for a feed before V2.
- **Outreach list** (British Triathlon, Stuweb + Castle Race Series, MYLAPS, RaceResult, UK Athletics): see `platform_review.md`. Not sent yet; the owner decides.
- **RunThrough** has opted out of AI agents. The owner runs the scraper, and its data stays out of LLM features. Asking for a feed is still the cleanest route.
- **Event Chip Timing** has the same AI-agent opt-out as RunThrough (both are RaceTec sites), so the same rules apply. Still unverified: whether the `StartPage.aspx` listing exists on this site. The site publishes gun time only, with no chip time.
- **UKResults** publishes no terms. Get explicit permission before V2 or public use.
- On this Mac the venv's editable `.pth` keeps getting the hidden flag, which breaks `uv run chipt-*` imports. The workarounds are in the README; root cause unknown.
- Holmfirth 10K 2023 uses different age categories and has no gender column, so its age groups don't line up with later years.
