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
- **Manual entry** on `feature/manual-entry` (stacked on `feature/more-races`): "Add a result" dialog + `POST /me/results/manual`. This is the route for IRONMAN, because the API portal lists no APIs (2026-11-10). Next: the owner enters their IRONMAN 70.3 Weymouth 2025 result
- V1 phase 2, step 2 (built on `feature/manual-import`, stacked on PR #8): `chipt-import` + British Triathlon importer. **Belvoir 2026 Triathlon Sprint imported** (243 results, idempotent)
- V1 phase 2, step 3 on `feature/provider-eventrac` (stacked on PR #9): **Eventrac** built and ingested (28 events, 6,312 results). race-results.co.uk is parked by the owner
- V1 phase 2, step 4 on `feature/more-races`: route-1 providers expanded to 241 events (RaceBest 58, UKResults 70, Eventrac 113); 85,669 results in total
- Later: API feeds (deferred), advanced analysis, better search
- **Cambridge Half Marathon 2025** (resultsbase RaceTec, `feature/provider-resultsbase-racetec`, stacked on `feature/manual-entry`): scraper built and checked offline on 330 synthetic pages. **Owner to run** `dump`, then `chipt-ingest resultsbase` twice
- RunThrough: the owner runs the scraper by hand (`list` → pin RIds → `dump` → ingest)

## Blockers / open questions
- **IRONMAN** has no usable API (the portal lists none), and its site is closed to scraping and imports. Results come in by manual entry. Asking IRONMAN for a feed is optional (outreach item 0).
- **resultsbase.net**: the `www` host is blocked by Cloudflare Turnstile and opts out `ClaudeBot`/`GPTBot` (route: manual import, or ask). The RaceTec host `results.resultsbase.net` is user-run (built 2026-11-10). It's unverified whether that host has a bot challenge, because the agent can't fetch results pages there.
- **British Triathlon** (the owner's priority for triathlon) is behind Cloudflare on every page. Route: manual import (phase 2 step 2); ask for a feed before V2.
- **Outreach list** (British Triathlon, Stuweb + Castle Race Series, MYLAPS, RaceResult, UK Athletics): see `platform_review.md`. Not sent yet; the owner decides.
- **RunThrough** has opted out of AI agents. The owner runs the scraper, and its data stays out of LLM features. Asking for a feed is still the cleanest route.
- **Event Chip Timing** has the same AI-agent opt-out as RunThrough (both are RaceTec sites), so the same rules apply. Still unverified: whether the `StartPage.aspx` listing exists on this site. The site publishes gun time only, with no chip time.
- **UKResults** publishes no terms. Get explicit permission before V2 or public use.
- On this Mac the venv's editable `.pth` keeps getting the hidden flag, which breaks `uv run chipt-*` imports. The workarounds are in the README; root cause unknown.
- Holmfirth 10K 2023 uses different age categories and has no gender column, so its age groups don't line up with later years.
