# CLAUDE.md
## Project Goals
**Current milestone:** V1 (MVP complete; see [V1 plan](docs/v1_plan.md)) - A hub for amateur athletes that aggregates their race results — currently scattered across many different timing/results platforms — into one place, and lets them analyse their performance over time.

**Sports covered:** running, cycling, swimming, triathlon (and duathlon).

**MVP scope:**
- Ingest ≥2 races from each of ≥2 hand-picked providers by scraping. MVP providers: **RaceBest** (racebest.com) and **UKResults** (ukresults.net). RunThrough and Event Chip Timing are user-run only because of an AI opt-out, and resultsbase is blocked by Cloudflare (see `docs/providers/`)
- Single user, no authentication: one hardcoded `athlete` row
- Search results by name (required) plus optional discipline, provider, race name and age group, then **claim** the results that belong to the user
- Analysis: a time series of the user's headline (chip) results within a comparison group of `(discipline, distance_label)`, e.g. running / 10K

**Out of scope:** payments, live/real-time tracking, splits (final results only), native mobile apps.

**Later milestones (don't build yet):** V1 = Next.js UI and API-based provider feeds; V2 = multiple users, auth, scheduled ingestion; Later = Claude API integration, social features, head-to-head comparison. See `project_spec.md` §3.

## Architecture Overview

Current repo contents:
```
chipt/
├── CLAUDE.md
├── README.md            # setup + run commands
├── project_spec.md      # single source of truth for requirements & design
├── brainstorm.md        # original goals/milestones notes
├── pyproject.toml       # uv project; scripts chipt-ingest, chipt-initdb, chipt-openapi
├── docker-compose.yml   # Postgres 16 on host port 5433
├── .env.example         # all config vars; copy to .env
├── docs/
│   ├── architecture.md  # components, data flow, API, schema
│   ├── changelog.md
│   ├── project_status.md
│   ├── v1_plan.md       # V1 roadmap + phase 1 (Next.js UI) plan
│   └── providers/       # per-provider legal posture + technical notes
├── web/                 # Next.js UI (Node 22, npm): app/ routes, components/ (ui/ = shadcn), lib/api (generated types + client), e2e/ (Playwright)
└── src/chipt/
    ├── config.py        # settings from .env
    ├── schemas.py       # canonical Pydantic models + API contract
    ├── db/              # schema.sql, init, session, ingest_repo (upserts), repository (queries), e2e_fixture (Playwright test athlete)
    ├── ingest/          # base.py, http.py (PoliteClient), normalise.py, cli.py, providers/<slug>.py (racetec.py = shared RaceTec base)
    ├── analysis/        # timeseries.py (pandas, pure)
    └── api/             # main.py (FastAPI), openapi.py (schema export for web/)
```

Components (from `project_spec.md` §5.3):
- **Ingestion layer**: one scraper module per provider, run as offline CLI jobs
- **PostgreSQL**: the canonical store
- **FastAPI backend**: `/search`, `/results/{id}`, `/me/results` (GET/POST/DELETE), `/analysis`
- **Frontend**: Next.js in `web/` (V1). The MVP's Streamlit UI was retired in V1 phase 1

**Data flow:**
race sites → provider scraper (`discover` → `fetch` → `parse` → `upsert`) → normaliser → PostgreSQL → FastAPI → Next.js UI

- Ingestion is **decoupled**: scrapers run as offline jobs that write to the DB, never on demand when a user searches. For MVP a "scheduled" job is a manually run CLI script per provider.
- Upserts are idempotent on `provider_id + external_id`.
- Store both the normalised records **and** the raw payload (`raw` JSONB), so parsing can be fixed without re-scraping.

**Canonical data model** (full detail in `project_spec.md` §5.4):
`provider` → `event` → `result`; `athlete` ← `claimed_result` → `result`
- Times are **chip time**, stored as integer `chip_time_seconds` and rendered as HH:MM:SS
- `age_group` is stored **as the race published it** (e.g. `V40`, `35-39`)
- `distance_label` (e.g. `10K`, `Marathon`, `Olympic`) is the **comparability key** for every discipline
- `distance_km` is set only for single-discipline events and is **null for multi-sport** events
- `athlete_name` is indexed with `pg_trgm` for fuzzy matching

## Design Style Guide

**Tech stack:**
| Layer | Choice |
|---|---|
| Backend / ingestion / analysis | Python: `httpx` + `BeautifulSoup` for static sites, `Playwright` for JS-rendered sites, `pandas` for analysis |
| API | FastAPI (Pydantic models double as the canonical schema) |
| Database | PostgreSQL with `pg_trgm` and JSONB (chosen over MongoDB; see spec §5.2) |
| Frontend | Next.js 15 (App Router) + React 19 + TypeScript, Tailwind v4, shadcn/ui (Radix, Nova preset), Recharts. Data fetching: TanStack Query; API types generated from FastAPI's OpenAPI (`openapi-typescript` + `openapi-fetch`); dark mode: `next-themes` |
| Auth (V2) | FastAPI + JWT, or Clerk / Supabase Auth (decide at V2) |
| LLM (Later) | Anthropic API (Claude) behind FastAPI |

**Visual style (V1):** Clean and minimal. Neutral shadcn/ui base, Geist font, and **one sporty accent: orange** (`--primary`: orange-700 in light mode for white-text contrast, orange-500 in dark mode). The accent is for primary actions, focus rings and chart series 1 only (charts use orange-600 in dark mode, validated with the `dataviz` skill's palette validator). Charts follow the `dataviz` skill: load it before building or changing any chart. Light, dark and system themes. Mobile-first: top nav on desktop, slide-out sheet on mobile. Theme tokens live in `web/app/globals.css`.

**Component patterns:**
- Every provider scraper implements the common interface `discover()`, `fetch(event)`, `parse(raw)` and `upsert()`, and lives in its own isolated module
- Analysis is rendered as a time-series chart per comparison group, with these metrics: finish time, pace (min/km, single-discipline only), trend, PB, and most recent result vs PB
- The analysis view defaults to the comparison group with the most claimed results

## Product and UX Guidelines

**Core UX principles:**
- Three core flows: **Find** (search returns candidates ranked by match confidence) → **Claim** (the user confirms which results are theirs) → **Analyse** (time series within a comparison group)
- Only compare like with like: same discipline **and** same `distance_label`
- Show the user something meaningful immediately (default to their largest comparison group)

**Copy tone:** Not yet defined.

## Constraints & Policies

**Security - MUST follow:**
- Never commit `.env`. All config goes in `.env`, and every new variable is documented in `.env.example`
- No secrets or API keys in code

**Scraping - MUST follow:**
- Check each provider's **ToS and robots.txt** before building a scraper, and document the legal posture per provider
- Respect `robots.txt`, rate-limit requests (`SCRAPER_RATE_LIMIT_SECONDS`), and set an honest User-Agent (`SCRAPER_USER_AGENT`)
- Cache raw responses (`SCRAPER_CACHE_DIR`) and fail softly per record
- Prefer providers that have APIs or permissive terms
- **Never bypass bot checks, CAPTCHAs or AI-agent opt-outs in robots.txt** (no browser-spoofing User-Agents, no replaying session cookies). Reject the provider, or have the owner run the scraper when only AI agents are opted out
- Data from providers that opt out of AI (currently RunThrough and Event Chip Timing) must not be sent to LLM features
- Run app commands with `src` on the path if `.pth` imports break (see README → Troubleshooting)

**Privacy:** Results are public, but take care when associating them with user accounts (V2+).

**Code quality:**
- Keep scrapers small and isolated per provider, because sites change and scrapers break
- Keep the canonical schema in Pydantic models

**Dependencies:** Stick to the stack listed above, and justify any new dependency against it.

**Deployment:** local only. Postgres runs in Docker, and FastAPI and the Next.js dev server run on the dev machine. Hosting is deferred to V1/V2.

## Repository Etiquette

**Branching:**
- ALWAYS create a new feature branch before starting major changes
- NEVER commit directly to `main`
- Branch naming: `feature/description` or `fix/description`

**Git workflow for major changes:**
1. Create a new branch: `git checkout -b feature/description`
2. Develop and commit on the feature branch
3. Test locally before pushing
4. Push the branch: `git push -u origin feature/description`
5. Create a PR to merge into `main`
6. Use the `update-docs-and-commit` slash command for commits to ensure docs are update alongside code changes.

**Commits:**
- Write clear commit messages describing the change
- Keep commits focussed on single changes

**Pull requests:**
- Create PRs for all changes to `main`
- NEVER force push to `main`
- Include descriptions of what changed and why

## Testing

**Automated (V1, light):** before every PR, `cd web && npm run check` (typecheck + lint + production build) and `npm run test:e2e` (Playwright smoke test of find → claim → analyse → unclaim) must pass. After any API schema change, run `npm run gen:api` and commit the regenerated types. No Python unit tests yet.

**E2E safety:** the smoke test runs as a throwaway athlete (`E2E_ATHLETE_ID`, default 900) on its own ports (API 8010, web 3010), created and deleted by `python -m chipt.db.e2e_fixture`. It refuses the real athlete id. Fixtures come from RaceBest only; never use data from AI-opted-out providers as fixtures.

**Manual test checklist:**
- [ ] Scraper successfully pulls race results
- [ ] Re-running a scraper doesn't create duplicates (idempotent upsert)
- [ ] Race results are searchable (fuzzy name match, plus filters)
- [ ] Results can be claimed and unclaimed
- [ ] Analysis time series shows correct chip times and pace for a comparison group
- [ ] Race results are presented in the UI

## Documentation
- [Project spec](project_spec.md) - Full requirements and tech details
- [Brainstorm](brainstorm.md) - Original goals and milestones notes
- [Changelog](docs/changelog.md) - Version history
- [Project status](docs/project_status.md) - Current progress
- [V1 plan](docs/v1_plan.md) - V1 roadmap and the phase 1 (Next.js UI) implementation plan
- [.env.example](.env.example) - All configuration variables
- Update files in the docs folder after major milestones and major additions to the project.
- Use the /update-docs-and-commit slash command when making commits
