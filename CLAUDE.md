# CLAUDE.md
## Project Goals
**Current milestone:** MVP - A hub for amateur athletes that aggregates their race results — currently scattered across many different timing/results platforms — into one place, and lets them analyse their performance over time.

**Sports covered:** running, cycling, swimming, triathlon (and duathlon).

**MVP scope:**
- Ingest ≥2 races from each of ≥2 hand-picked providers by scraping. MVP providers: https://www.resultsbase.net and https://results.runthrough.co.uk
- Single user, no authentication: one hardcoded `athlete` row
- Search results by name (required) plus optional discipline, provider, race name and age group, then **claim** the results that belong to the user
- Analysis: a time series of the user's headline (chip) results within a comparison group of `(discipline, distance_label)`, e.g. running / 10K

**Out of scope:** payments, live/real-time tracking, splits (final results only), native mobile apps.

**Later milestones (don't build yet):** V1 = Next.js UI and API-based provider feeds; V2 = multiple users, auth, scheduled ingestion; Later = Claude API integration, social features, head-to-head comparison. See `project_spec.md` §3.

## Architecture Overview

Current repo contents (no application code yet):
```
chipt/
├── CLAUDE.md
├── project_spec.md      # single source of truth for requirements & design
├── brainstorm.md        # original goals/milestones notes
├── .env.example         # all config vars; copy to .env
├── .gitignore
└── docs/
    ├── changelog.md
    └── project_status.md
```

Planned components (from `project_spec.md` §5.3):
- **Ingestion layer**: one scraper module per provider, run as offline CLI jobs
- **PostgreSQL**: the canonical store
- **FastAPI backend**: `/search`, `/results/{id}`, `/me/results` (GET/POST/DELETE), `/analysis`
- **Frontend**: Streamlit (MVP), replaced by Next.js in V1

**Data flow:**
race sites → provider scraper (`discover` → `fetch` → `parse` → `upsert`) → normaliser → PostgreSQL → FastAPI → Streamlit UI

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
| Frontend (MVP) | Streamlit; the UI is throwaway |
| Frontend (V1+) | Next.js + TypeScript, TailwindCSS, shadcn/ui, Recharts/Visx |
| Auth (V2) | FastAPI + JWT, or Clerk / Supabase Auth (decide at V2) |
| LLM (Later) | Anthropic API (Claude) behind FastAPI |

**Visual style:** Not yet defined. The MVP uses default Streamlit; V1 targets a "slick, user-centric UI" built with Tailwind + shadcn/ui.

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

**Privacy:** Results are public, but take care when associating them with user accounts (V2+).

**Code quality:**
- Keep scrapers small and isolated per provider, because sites change and scrapers break
- Keep the canonical schema in Pydantic models

**Dependencies:** Stick to the stack listed above, and justify any new dependency against it.

**Deployment (MVP):** local only. Postgres runs in Docker, and FastAPI and Streamlit run on the dev machine. Hosting is deferred to V1/V2.

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

**MVP approach:** Manual testing (no automated tests yet)

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
- [.env.example](.env.example) - All configuration variables
- Update files in the docs folder after major milestones and major additions to the project.
- Use the /update-docs-and-commit slash command when making commits
