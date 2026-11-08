# Architecture

This document describes the high-level system architecture, data flows, and component relationships for Chipt.

## System Overview

Chipt is a Python monorepo (`src/chipt/`, managed with uv) with four parts:

| Part | Tech | Entry point |
|---|---|---|
| Ingestion (offline jobs) | httpx + BeautifulSoup | `uv run chipt-ingest <provider>` |
| Database | PostgreSQL 16 in Docker (`docker-compose.yml`, host port 5433), `pg_trgm`, JSONB | `uv run chipt-initdb` |
| Backend API | FastAPI + async SQLAlchemy Core (asyncpg), pandas for analysis | `uv run uvicorn chipt.api.main:app --app-dir src` |

Configuration comes from `.env`, loaded by `chipt.config.Settings` (pydantic-settings). Every variable is documented in `.env.example`.

## Data Flow

```
provider site ──▶ PoliteClient (robots.txt, rate limit, honest UA, retries, raw cache in SCRAPER_CACHE_DIR)
              ──▶ Scraper.discover() → fetch(ref) → parse(ref, raw) → [ParsedEvent]
              ──▶ ingest_repo.upsert_*  ──▶ PostgreSQL
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

### API Layer

`chipt.api.main` (FastAPI). Responses use the models in `chipt.schemas`, and CORS origins come from `CORS_ALLOWED_ORIGINS`.

| Method | Path | Notes |
|---|---|---|
| GET | `/health` | `{"status":"ok"}` |
| GET | `/search` | `name` (required), `discipline`, `provider` (slug), `race` (substring), `age_group`, `limit`. Returns `SearchResultOut[]` ranked by score |
| GET | `/results/{id}` | `ResultDetailOut`, including `raw` |
| GET | `/me/results` | The default athlete's claimed results, newest first |
| POST | `/me/results` | `{"result_id"}` → 201. Idempotent |
| DELETE | `/me/results/{id}` | 204. Idempotent |
| GET | `/analysis` | `discipline` + `distance_label`, or neither for the largest group. 404 if nothing is claimed |
| GET | `/filters` | Distinct disciplines, providers, races and age groups for the UI dropdowns |

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
| `chipt.db.repository` | Read queries: search, claims, comparison groups, filters |
| `chipt.analysis.timeseries` | Time-series metrics for a comparison group (pandas) |
