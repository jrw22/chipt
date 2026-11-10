# Architecture

This document describes the high-level system architecture, data flows, and component relationships for Chipt.

## System Overview

Chipt is a Python monorepo (`src/chipt/`, managed with uv) with four parts:

| Part | Tech | Entry point |
|---|---|---|
| Ingestion (offline jobs) | httpx + BeautifulSoup | `uv run chipt-ingest <provider>` |
| Database | PostgreSQL 16 in Docker (`docker-compose.yml`, host port 5433), `pg_trgm`, JSONB | `uv run chipt-initdb` |
| Backend API | FastAPI + async SQLAlchemy Core (asyncpg), pandas for analysis | `uv run uvicorn chipt.api.main:app --app-dir src` |
| Frontend | Next.js 15 + Tailwind + shadcn/ui in `web/`; talks to the API over HTTP only | `cd web && npm run dev` (http://localhost:3000) |
| Smoke tests | Playwright (`web/e2e/`) against the real local DB as a throwaway test athlete | `cd web && npm run test:e2e` |

Configuration comes from `.env`, loaded by `chipt.config.Settings` (pydantic-settings). Every variable is documented in `.env.example`.

## Data Flow

```
provider site ──▶ PoliteClient (robots.txt, rate limit, honest UA, retries, raw cache in SCRAPER_CACHE_DIR)
              ──▶ Scraper.discover() → fetch(ref) → parse(ref, raw) → [ParsedEvent]
              ──▶ ingest_repo.upsert_*  ──▶ PostgreSQL
```

Manual import (route 3, for bot-checked sites):

```
owner's browser ──▶ saved file in imports/<provider>/ ──▶ chipt-import <provider> <files> [--date]
                ──▶ FileImportScraper.discover() (the files) → fetch() (read file, never the network) → parse()
                ──▶ the same ingest_repo upserts ──▶ PostgreSQL   (provider.ingest_type = 'manual')
```

- Ingestion is decoupled. Scrapers run as manual CLI jobs and never on demand.
- Upserts are idempotent. Events are keyed on `(provider_id, external_id)` and results on
  `(event_id, athlete_name, chip_time_seconds)`. Re-ingestion updates rows in place, so result ids
  (and therefore claims) stay stable.
- Each `event` and `result` row keeps the original payload in `raw` JSONB.

### Database schema (`src/chipt/db/schema.sql`)

`provider` 1─* `event` 1─* `result` *─* `athlete` (through `claimed_result`)

- `event.discipline`: enum `running | cycling | swimming | triathlon | duathlon`.
- `event.distance_label`: the comparability key. `distance_km` is NULL for multi-sport events.
- `result.chip_time_seconds`: integer, NOT NULL.
- `result.athlete_name`: indexed with a GIN `gin_trgm_ops` index.
- `athlete`: holds the single MVP athlete, seeded by `chipt-initdb` from `DEFAULT_ATHLETE_ID` and
  `DEFAULT_ATHLETE_DISPLAY_NAME`.

## Component Architecture

### Frontend Components

**Next.js (`web/`).** It replaced the MVP's Streamlit UI in V1 phase 1 (see `docs/v1_plan.md`).
- `app/layout.tsx`: shell with a sticky top nav (Dashboard, Find results, My results, Analysis), a mobile sheet menu, a light/dark/system theme toggle, and an API-unreachable banner that polls `/health`.
- `lib/api/schema.d.ts`: TypeScript types generated from FastAPI's OpenAPI schema (`npm run gen:api`, which runs `uv run chipt-openapi` and then `openapi-typescript`). `lib/api/client.ts`: an `openapi-fetch` client plus `unwrap()`, which turns failures into `ApiError`. `lib/api/hooks.ts`: TanStack Query hooks and query keys.
- `lib/format.ts`: duration, signed delta, pace and date formatting (ported from the Streamlit helpers).
- **Find results** (`/find`): `components/find/`. The search (name plus discipline/provider/race/age-group searchable comboboxes from `/filters`) lives in the URL query string, so it can be refreshed, bookmarked and navigated with back/forward. Candidates are grouped by event (events ordered by their best match, rows by score), each with a match %, time (`TimeDisplay` marks gun or unlabelled times), category, position and a DNF badge. Ticking or unticking rows collects changes. A sticky bar then saves them as POST/DELETE `/me/results` calls (`useSaveClaims`), shows a toast, and invalidates every claim-dependent query (`search`, `me`, `analysis`, `result`).
- **My results** (`/results`): `components/results/`. The claimed results are shown as a sortable table on desktop (date, race, time) and as cards on mobile, with a discipline filter. The filter and sort live in the URL. Remove is immediate, with an Undo action on the toast (`useUnclaimWithUndo`) instead of a confirm dialog.
- **Result detail** (`/results/[id]`): time (chip/gun aware) and pace, plus overall/gender/category positions as "N of M" with "Top X%". Claim/remove toggle, a "Compare" link to the analysis for that comparison group, and a link to the provider's page. The raw payload is not shown (splits are out of scope).
- **Analysis** (`/analysis?discipline=&distance_label=`): `components/analysis/`. A group picker (one filter row above everything it scopes), stat tiles (PB, latest race vs PB, trend per year, race count), a finish-time chart, a pace chart (single-discipline groups only), and a table of every race. Charts (`TimeSeriesChart`, Recharts via shadcn's chart wrapper) follow the `dataviz` skill: one 2px accent line, 8px dots with a 2px surface ring, no legend (the card title names the single series), direct labels only on the PB and the latest race, solid hairline grid, y-ticks on round time steps, and a crosshair with a value-first tooltip. The table means the tooltip never gates a value. Refetches keep the previous render at reduced opacity.
- **Dashboard** (`/`): `components/dashboard/`, using `/me/summary`. Totals tiles, one PB card per comparison group (PB, sparkline with history in the de-emphasis grey and the latest race in the accent, latest vs PB, trend) linking to its analysis, and recent races. Welcome empty state.
- **Chart colour:** `--chart-1` is orange-700 in light mode and **orange-600 in dark mode**. Orange-500 (the dark-mode button colour) failed the dataviz validator's dark lightness band, while orange-600 passes. Both pass contrast against the card surface.
- Pages are client components that fetch through TanStack Query. There are no Next server actions and no direct DB access.

**Smoke tests (`web/e2e/`).** `playwright.config.ts` starts its own API (port 8010, `DEFAULT_ATHLETE_ID=900`) and Next dev server (port 3010, `NEXT_DIST_DIR=.next-e2e`). Global setup runs `python -m chipt.db.e2e_fixture setup`: it creates the throwaway athlete and writes a fixture, one RaceBest finisher whose name is unique in the DB. The test then walks the dashboard empty state → search → claim → My results → detail → Compare/analysis → dashboard PB card → remove + undo → remove. Global teardown deletes the athlete and its claims.

### API Layer

`chipt.api.main` (FastAPI). Responses use the models in `chipt.schemas`, and CORS origins come from `CORS_ALLOWED_ORIGINS`.

| Method | Path | Notes |
|---|---|---|
| GET | `/health` | `{"status":"ok"}` |
| GET | `/search` | `name` (required), `discipline`, `provider` (slug), `race` (substring), `age_group`, `limit`. Returns `SearchResultOut[]` ranked by score |
| GET | `/results/{id}` | `ResultDetailOut`, including `raw` and field sizes for "N of M": `event_finishers`, `gender_finishers`, `category_finishers` (finishers only; gender/category are null when the result has none) |
| GET | `/me/results` | The default athlete's claimed results, newest first |
| POST | `/me/results` | `{"result_id"}` → 201. Idempotent |
| DELETE | `/me/results/{id}` | 204. Idempotent |
| GET | `/analysis` | `discipline` + `distance_label`, or neither for the largest group. 404 if nothing is claimed |
| GET | `/me/summary` | Dashboard data in one call: `totals` (results incl. DNFs, races, disciplines, providers, first/latest race), `groups` (each comparison group's `analyse_group` output without the group list, largest first) and `recent` (latest 5 claimed results). Empty rather than 404 when nothing is claimed |
| GET | `/filters` | Distinct disciplines, providers, races and age groups for the UI dropdowns |

- **`time_source`** (on every result): `chip`, `gun` or `unspecified`, i.e. what `chip_time_seconds` actually holds. It's derived in SQL (`_TIME_SOURCE` in `chipt.db.repository`) from the raw payload. RaceTec scrapers record `_time_source`, and RaceBest/UKResults record the source column in `_chipt_time_source`. A bare "Time" column becomes `unspecified`.
- **Search score:** `GREATEST(similarity(name), word_similarity(name))`. The WHERE clause uses the
  `%` / `<%` operators, so the GIN trigram index is used. The threshold is
  `SEARCH_SIMILARITY_THRESHOLD`, applied per transaction.
- **Analysis:** `chipt.analysis.timeseries.analyse_group` is pure, with no DB access. It returns
  points sorted by date; pace only when `distance_km` is set; the PB; most recent vs PB; and a trend
  from a linear fit of seconds against years. The trend is "improving" when the slope is below −1% of
  the mean time per year and "declining" when it is above +1%. With fewer than 2 points it is
  "insufficient_data".

### Library Modules

| Module | Responsibility |
|---|---|
| `chipt.config` | Typed settings from `.env` |
| `chipt.schemas` | Canonical Pydantic models (`ProviderIn`, `EventIn`, `ResultIn`, `ParsedEvent`) and the API response contract |
| `chipt.db.schema.sql` / `db.init` | Idempotent DDL plus the athlete seed |
| `chipt.db.session` | Async SQLAlchemy Core engine and the `get_conn` FastAPI dependency |
| `chipt.db.ingest_repo` | Idempotent provider/event/result upserts |
| `chipt.ingest.http` | `PoliteClient`: robots.txt, per-host rate limit, User-Agent, retries, on-disk raw cache |
| `chipt.ingest.base` | `BaseScraper` interface (`discover`/`fetch`/`parse`, shared `upsert`/`run`) and `EventRef` |
| `chipt.ingest.normalise` | Shared normalisation: time → seconds, distance label/km, discipline inference, name cleaning |
| `chipt.ingest.cli` | Provider registry (`PROVIDERS`) and the `chipt-ingest` command |
| `chipt.ingest.providers.*` | One isolated scraper per provider (see `docs/providers/`) |
| `chipt.ingest.providers.racetec` | Shared base for RaceTec-hosted sites (RunThrough, Event Chip Timing): header-driven parser, GridView postback pagination, `list`/`dump` helper CLI |
| `chipt.db.repository` | Read queries: search, claims, comparison groups, filters |
| `chipt.analysis.timeseries` | Time-series metrics for a comparison group (pandas) |
