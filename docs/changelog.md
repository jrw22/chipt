# Changelog

All notable changes to Chipt will be documented in this file. 

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- UK results-platform review (`docs/providers/platform_review.md`): about 30 platforms, triathlon-first, each with robots.txt / terms / bot-protection / delivery evidence and an **access route** (direct scrape, user-run, manual import, trace to source, permission, reject), plus a build shortlist and outreach list. Also `docs/providers/britishtriathlon.md` and the phase 2 plan (`docs/v1_phase2_plan.md`).
- Playwright smoke test (`web/e2e/`, `npm run test:e2e`): dashboard empty state → find → claim → my results → detail → analysis → dashboard PB → remove + undo. It runs on its own ports as a throwaway test athlete (`python -m chipt.db.e2e_fixture`, which refuses the real athlete id), with fixtures from RaceBest only.
- V1 web app: **Analysis** page (`/analysis`). Comparison-group picker kept in the URL, stat tiles (PB, latest vs PB, trend, races), finish-time and pace charts (crosshair tooltip, PB and latest labelled, clean time ticks), and a table of every race. Empty and unknown-group states.
- V1 web app: **Dashboard** (`/`). Totals, a PB card with sparkline per comparison group, recent races, and a welcome empty state.
- API: `GET /me/summary` returns totals, per-group headline numbers and recent results in one call for the dashboard.
- V1 web app: **My results** page (`/results`). Sortable table on desktop and cards on mobile, discipline filter, pace and position. Remove with Undo. Empty state links to Find.
- V1 web app: **result detail** page (`/results/[id]`). Time and pace, overall/gender/category positions as "N of M" with "Top X%" or "Winner", claim/remove, Compare link to analysis, and a not-found state.
- API: `/results/{id}` returns `event_finishers`, `gender_finishers` and `category_finishers` (finishers only) for "N of M" positions.
- V1 web app: **Find results** page (`/find`). Name search plus searchable filters, with the search kept in the URL. Results are grouped by race with match %, time, category, position and DNF badges. Tick/untick to claim or unclaim, then save from a sticky bar with toast feedback. Loading, empty and error states; mobile layout.
- API: `time_source` (`chip` / `gun` / `unspecified`) on every result, so the UI can say when a time isn't a chip time.
- V1 Next.js app scaffold in `web/` (Next.js 15, React 19, Tailwind v4, shadcn/ui on Radix with the Nova preset, Node 22). It has an app shell with responsive nav, a light/dark/system theme, an orange accent and an API-unreachable banner, plus placeholder pages for Dashboard, Find results, My results and Analysis.
- Typed API client for the web app: `uv run chipt-openapi` exports FastAPI's OpenAPI schema, and `npm run gen:api` turns it into TypeScript types used through `openapi-fetch` and TanStack Query.
- V1 implementation plan (`docs/v1_plan.md`): roadmap for V1 and a detailed plan for phase 1, the Next.js UI.
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
- RaceTec `RACES` entries are validated. A malformed entry, two entries run together by a missing comma, or a race listed twice now raises a clear error and is no longer silently mislabelled.
- Aquabike events get their own distance labels (e.g. `Aquabike Middle Distance (70.3)`), so they're never compared with triathlons.
- resultsbase stub scraper, which ingests nothing because results pages are behind Cloudflare Turnstile.
- Per-provider legal posture and technical notes in `docs/providers/`.
- FastAPI backend: `/search` (pg_trgm fuzzy name match plus filters), `/results/{id}`, `/me/results` claim/unclaim, `/analysis` (PB, most recent vs PB, pace, linear trend; defaults to the largest comparison group), `/filters`, `/health`.
- Streamlit UI with three pages: Find & Claim, My Results and Analysis (time-series chart, PB/trend tiles, pace).

### Changed
- Spec §8: the MVP's accept/reject rule is replaced by access routes, and the provider table now lists every reviewed platform with its route. V1 phase 2 is redefined: the API-feeds shift is deferred. resultsbase now also opts out `ClaudeBot`/`GPTBot`, and Sporthive's robots.txt now allows results (but the MYLAPS terms forbid copying).
- `CORS_ALLOWED_ORIGINS` now defaults to the web app only (`http://localhost:3000`). Next.js `distDir` can be overridden with `NEXT_DIST_DIR`, so the smoke test's dev server doesn't clash with yours.
- `.env.example`: Postgres host port is now 5433, so it doesn't clash with a native Postgres on 5432. Added `PROVIDER_RACEBEST_BASE_URL`, `PROVIDER_UKRESULTS_BASE_URL` and `PROVIDER_EVENTCHIPTIMING_BASE_URL`.
- Analysis (comparison groups and time series) excludes non-finishers. DNFs can still be found, claimed and listed.
- RunThrough scraper is now a thin subclass of the shared RaceTec base. Behaviour and external ids are unchanged.

### Removed
- Streamlit UI (`src/chipt/ui/`), the `streamlit` dependency (and Altair with it), and the `STREAMLIT_SERVER_PORT` / `API_BASE_URL` settings. The Next.js app in `web/` replaces it at full parity, except the raw-payload viewer, which was dropped on purpose (raw data is still in the DB and in `/results/{id}`).
