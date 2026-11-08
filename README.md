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
uv run chipt-ingest resultsbase       # hand-picked races for a provider
uv run chipt-ingest runthrough
uv run chipt-ingest runthrough --url <race-results-url>   # one specific race
```
Re-running is idempotent. Raw responses are cached in `SCRAPER_CACHE_DIR`, so re-parsing doesn't re-fetch.
Per-provider legal posture and notes: [docs/providers/](docs/providers/).

## Run the app
```bash
uv run uvicorn chipt.api.main:app --app-dir src --reload   # API on http://127.0.0.1:8000 (docs at /docs)
uv run streamlit run src/chipt/ui/app.py            # UI on http://localhost:8501
```

## Troubleshooting
- **`ModuleNotFoundError: No module named 'chipt'`** under `uv run`: on macOS the editable-install `.pth`
  file in `.venv` can get the `hidden` flag, and Python ≥3.11.8 skips hidden `.pth` files. Fix with
  `chflags nohidden .venv/lib/python3.*/site-packages/*.pth`. The API (`--app-dir src`) and the
  Streamlit app add `src/` to the path themselves, so only the `chipt-*` CLI commands are affected;
  `PYTHONPATH=src uv run python -m chipt.ingest.cli <provider>` also works.

## Layout
```
src/chipt/
├── config.py            # settings from .env
├── schemas.py           # canonical Pydantic models + API contract
├── db/                  # schema.sql, init, session, ingest_repo (upserts), repository (queries)
├── ingest/              # base interface, polite HTTP client, normalise helpers, CLI, providers/
├── analysis/            # time-series metrics (pandas)
├── api/                 # FastAPI app
└── ui/                  # Streamlit app
```
