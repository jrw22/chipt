# Project status

## Current milestone
**MVP** (see `project_spec.md` §3)

## Done
- [x] Project scaffold: uv project, Docker Postgres (port 5433), `.env` settings
- [x] Canonical schema (Pydantic + SQL), idempotent upserts, `pg_trgm` index, seeded single athlete
- [x] Shared scraper interface, polite HTTP client, normalisation helpers, ingest CLI
- [x] Backend API: search, claims and analysis, tested end to end on real data
- [x] **Ingest ≥2 races from ≥2 providers.** RaceBest (12 events, 3,876 results) and UKResults (7 events, 2,537 results). Re-running is idempotent.

## In progress
- Streamlit UI
- RunThrough: the owner runs the scraper by hand (`list` → pin RIds → `dump` → ingest)

## Next up
- Search → claim → analysis flows

## Blockers / open questions
- **resultsbase.net** is blocked by Cloudflare Turnstile. Next step: ask info@resultsbase.net for access or a feed.
- **RunThrough** has opted out of AI agents. The owner runs the scraper, and its data stays out of LLM features. Asking for a feed is still the cleanest route.
- **UKResults** publishes no terms. Get explicit permission before V2 or public use.
- Holmfirth 10K 2023 uses different age categories and has no gender column, so its age groups don't line up with later years.
