# Project status

## Current milestone
**MVP** (see `project_spec.md` §3)

## Done
- [x] Project scaffold: uv project, Docker Postgres (port 5433), `.env` settings
- [x] Canonical schema (Pydantic + SQL), idempotent upserts, `pg_trgm` index, seeded single athlete
- [x] Shared scraper interface, polite HTTP client, normalisation helpers, ingest CLI

## In progress
- Provider scrapers, backend API, Streamlit UI

## Next up
- Ingest ≥2 races from ≥2 providers
- Search → claim → analysis flows

## Blockers / open questions
- None yet.
