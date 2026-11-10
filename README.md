# Chipt — Results Viewer (MVP)

Aggregates amateur race results from multiple timing providers into one place, lets you find and claim
your results, and charts your performance over time. See [project_spec.md](project_spec.md).

## Prerequisites
- [uv](https://docs.astral.sh/uv/) (Python 3.11+)
- Docker Desktop (for Postgres)

## Setup
```bash
cp .env.example .env          # then edit values (DB password, scraper User-Agent, your display name)
docker compose up -d          # Postgres 16 on localhost:5433
uv sync                       # install deps (add `--extra js` if a scraper needs Playwright)
uv run chipt-initdb           # create schema + seed the single MVP athlete (safe to re-run)
```

## Ingest results (offline jobs)
```bash
uv run chipt-ingest --list            # configured providers
uv run chipt-ingest racebest          # hand-picked races for a provider
uv run chipt-ingest ukresults
uv run chipt-ingest eventrac          # Lancing / Worthing 10K, Bedgebury Half & 10K (multi-year)
uv run chipt-ingest racebest --url <race-results-url>     # one specific race
# runthrough, eventchiptiming, resultsbase: run by hand only (AI opt-out), see docs/providers/
#   e.g. uv run chipt-ingest resultsbase   # Cambridge Half 2025, ~330 pages, ~11 min first time
```
Re-running is idempotent. Raw responses are cached in `SCRAPER_CACHE_DIR`, so re-parsing doesn't re-fetch.
Per-provider legal posture and notes: [docs/providers/](docs/providers/).

## Import saved results pages (manual import)
For sites that block automated access (e.g. British Triathlon), save the results page in your own browser
into `imports/<provider>/` (gitignored), then:
```bash
uv run chipt-import --list
uv run chipt-import britishtriathlon imports/BritishTriathlon/belvoir-2026-sprint-p*.html \
    --date 2026-07-18 --race "Triathlon Sprint" --dry-run   # check first, then drop --dry-run
```
How to save each provider's pages is in its `docs/providers/<slug>.md`. Re-importing is idempotent.

## Add a result by hand (manual entry)
For platforms Chipt can't read at all (e.g. IRONMAN: no API, scraping forbidden), use **My results →
Add a result** in the web app, and copy your race, date, distance and chip time from the results page.
The result is filed under "Manual entry" and claimed straight away. See [docs/providers/ironman.md](docs/providers/ironman.md).

## Run the app
Two processes: the FastAPI backend and the Next.js web app (needs Node 22; `nvm use` reads `web/.nvmrc`).
```bash
uv run uvicorn chipt.api.main:app --app-dir src --reload   # API on http://127.0.0.1:8000 (docs at /docs)
cd web && npm install && npm run dev                        # UI on http://localhost:3000
```
Override the API URL with `NEXT_PUBLIC_API_BASE_URL` in `web/.env.local`.

## Checks and tests
```bash
cd web
npm run check      # typecheck + lint + production build (run before every PR)
npm run test:e2e   # Playwright smoke test: find → claim → analyse → unclaim
npm run gen:api    # regenerate TypeScript API types after changing src/chipt/schemas.py or the API
```
The smoke test needs Postgres running with RaceBest ingested (`uv run chipt-ingest racebest`). It starts
its own API and web servers on ports 8010/3010, so it doesn't clash with your dev servers. It also runs as a
throwaway test athlete (created and deleted by `python -m chipt.db.e2e_fixture`), so your claims are never
touched. First run only: `npx playwright install chromium`.

## Troubleshooting
- **`ModuleNotFoundError: No module named 'chipt'`** under `uv run`: on macOS the editable-install `.pth`
  file in `.venv` can get the `hidden` flag, and Python ≥3.11.8 skips hidden `.pth` files. Fix with
  `chflags nohidden .venv/lib/python3.*/site-packages/*.pth`. The API (`--app-dir src`) adds `src/`
  to the path itself, so only the `chipt-*` CLI commands are affected;
  `PYTHONPATH=src uv run python -m chipt.ingest.cli <provider>` also works.

## Layout
```
src/chipt/
├── config.py            # settings from .env
├── schemas.py           # canonical Pydantic models + API contract
├── db/                  # schema.sql, init, session, ingest_repo (upserts), repository (queries)
├── ingest/              # base interface, polite HTTP client, normalise helpers, CLI, providers/
├── analysis/            # time-series metrics (pandas)
└── api/                 # FastAPI app (+ openapi.py schema export for web/)
web/                     # Next.js app: app/ routes, components/, lib/api (generated types), e2e/ (Playwright)
```
