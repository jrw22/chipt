# Changelog

All notable changes to Chipt will be documented in this file. 

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Project scaffold: `pyproject.toml` (uv), `docker-compose.yml` (Postgres 16 on host port 5433), `README.md` with setup steps and run commands.
- Typed settings loaded from `.env` (`chipt.config`).
- Canonical Pydantic schema and API contract (`chipt.schemas`).
- PostgreSQL schema with `pg_trgm` name index, plus `chipt-initdb` to apply it and seed the single MVP athlete.
- Idempotent ingest upserts, the `BaseScraper` interface, the `PoliteClient` HTTP client (robots.txt, rate limit, honest UA, retries, raw cache), shared normalisation helpers and the `chipt-ingest` CLI.
- Provider scrapers. **RaceBest**: Holmfirth 10K 2023–26, Vale of York Half & 10K 2024–25, Harrogate Triathlon 2025–26. **UKResults**: Guy Fawkes 10 2024–26, Thirteen Arches Half 2025–26, Darley Moor Duathlon 2025–26. Together these ingest 19 events and 6,413 results, idempotently.
- RunThrough scraper (header-driven parser plus `list`/`dump` helpers), written without fetching the site and meant to be run by the project owner.
- resultsbase stub scraper, which ingests nothing because results pages are behind Cloudflare Turnstile.
- Per-provider legal posture and technical notes in `docs/providers/`.

### Changed
- `.env.example`: Postgres host port is now 5433, so it doesn't clash with a native Postgres on 5432. Added `PROVIDER_RACEBEST_BASE_URL` and `PROVIDER_UKRESULTS_BASE_URL`.
