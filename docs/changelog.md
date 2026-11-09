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
- Event Chip Timing scraper (`eventchiptiming`, results.eventchiptiming.com, RaceTec client 16202), with race `10316:1` pinned. Like RunThrough, it was written without fetching any results pages and is user-run only because of an AI-agent opt-out in robots.txt.
- Shared RaceTec base scraper (`chipt.ingest.providers.racetec`) used by RunThrough and Event Chip Timing. It supports `EId` sub-events (race specs `RId` or `RId:EId`), and its `dump` helper lists a race's sub-events.
- RaceTec race specs can pin a distance (`"RId:EId=<distance>"`) for pages that don't name it. The parser splits combined `Cat Pos (Gen Pos)` columns into category and gender rank, and `dump` prints a value-free `Columns` shape summary that's safe to share.
- RaceTec pagination follows any pager style (GET page links such as `PageNo=2`, or `__doPostBack` with any argument), stops if a page repeats, and `dump` prints the pager links it found. Grafman had 245 finishers across several pages and now ingests all of them, not just the first 50.
- RaceTec: when a column header repeats (`Name`, `Gun Time`), each field uses the first non-empty copy. Time cells may carry extra text, and skip logs give the reason plus value-free cell shapes.
- RaceTec: in a race that publishes positions, a row with a time but no position is stored as a DNF (`finisher = false`).
- Aquabike events get their own distance labels (e.g. `Aquabike Middle Distance (70.3)`), so they're never compared with triathlons.
- resultsbase stub scraper, which ingests nothing because results pages are behind Cloudflare Turnstile.
- Per-provider legal posture and technical notes in `docs/providers/`.
- FastAPI backend: `/search` (pg_trgm fuzzy name match plus filters), `/results/{id}`, `/me/results` claim/unclaim, `/analysis` (PB, most recent vs PB, pace, linear trend; defaults to the largest comparison group), `/filters`, `/health`.
- Streamlit UI with three pages: Find & Claim, My Results and Analysis (time-series chart, PB/trend tiles, pace).

### Changed
- `.env.example`: Postgres host port is now 5433, so it doesn't clash with a native Postgres on 5432. Added `PROVIDER_RACEBEST_BASE_URL`, `PROVIDER_UKRESULTS_BASE_URL` and `PROVIDER_EVENTCHIPTIMING_BASE_URL`.
- Analysis (comparison groups and time series) excludes non-finishers. DNFs can still be found, claimed and listed.
- RunThrough scraper is now a thin subclass of the shared RaceTec base. Behaviour and external ids are unchanged.
