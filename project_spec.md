# Results Viewer — Project Specification

> **Status:** Draft v0.1 · **Last updated:** 2026-11-07
> **Purpose:** This document captures *what* I want to build and *how* I want to build it. It is the single source of truth for the project. Sections marked **🟡 Open question** need a decision; **💡 Recommendation** records a proposed default.

---

## 1. Overview

### 1.1 Elevator pitch
A hub for amateur athletes that aggregates their race results — currently scattered across many different timing/results platforms — into one place, and lets them analyse their performance over time and (later) against other athletes.

### 1.2 Vision
Race results for running, cycling, swimming, and triathlon are published by many different providers on many different platforms. There is no single place for an athlete to see their whole competitive history or track progress. Results Viewer solves this by ingesting results from multiple providers, normalising them into one consistent model, letting a user find and claim the results that are theirs, and surfacing analysis of their performance across events and over time.

---

## 2. Product requirements

### 2.1 Who is the product for?
Amateur athletes competing in **running, cycling, swimming, and triathlon** races.

### 2.2 What problems does it solve?
1. **Fragmentation** — results are spread across many platforms because different race providers publish on different results systems. There is no single view of an athlete's history.
2. **No progress tracking** — it is hard to compare a result against past results of the same type, or (later) against other athletes.

### 2.3 What does the product do?
Brings results together into a per-user **hub** of race results, letting the user easily **find**, **see**, and **analyse** their results.

### 2.4 Scope / non-goals
- ❌ **No payment mechanism** (explicitly out of scope).
- ❌ No live/real-time race tracking — results are **final results only**, at a high level (no splits for now).
- ❌ No mobile-native apps (web only).

---

## 3. Milestones

### MVP
- Ingest **≥2 races from each of ≥2 race providers** into an initial dataset.
  - Providers are **hand-picked and scraped** (I specify the results sites I want; we build scrapers for them).
- **Single user**, no authentication.
- User can **search** race results by **name, age (group), sport/discipline, race provider, and race name** to identify and select results that are theirs.
- **Initial analysis:** compare the user's **headline results from events of the same discipline over a time series** (e.g. running finish times over the years).

### V1
- Slick, user-centric UI (Next.js frontend).
- **Shift from scraping toward APIs:** produce a **prioritised list of results platforms that expose APIs**, and migrate those providers from scrapers to an **API-based data feed**.
- Database expanded to more providers and more races per provider.
- More advanced analysis.
- Improved search/matching.

### V2
- **Multiple users.**
- **Auth & accounts** — login, and persist a user's claimed results between sessions.
- Optimised backend — storage, scraping/ingestion cadence, scheduling.

### Later
- **LLM integration** (Anthropic / Claude API) for advanced analysis and smarter result-finding.
- **Social** — search and view other users' results.
- **Cross-analysis** — compare two users' results head-to-head.

---

## 4. Key user flows (MVP)

1. **Find my results** — user enters search terms (name + optional discipline/provider/race/age group). System returns candidate results ranked by match confidence.
2. **Claim my results** — user selects the results that are genuinely theirs; these are saved to their profile as "my results".
3. **Analyse** — user views a time series comparing headline results within a discipline (and comparable distance), e.g. 10K finish time year over year.

> **✅ Decided (identity in MVP):** A **single hardcoded profile** — one `athlete` row in the DB; `claimed_result` links results to it. Auth and multiple users arrive in V2.

---

## 5. Technical design

### 5.1 Stack headlines

| Layer | Choice | Notes |
|---|---|---|
| Language (backend/ingest/analysis) | **Python** | `httpx` + `BeautifulSoup` for static sites, `Playwright` for JS-rendered sites, `pandas` for analysis. |
| Backend API | **FastAPI** | Async, Pydantic models double as the canonical schema, auto OpenAPI docs. |
| Database | **PostgreSQL** | See §5.2 for the decision rationale. |
| Frontend (MVP) | **Streamlit** (retired in V1 phase 1) | See §5.9. |
| Frontend (V1+) | **Next.js (React) + TypeScript**, TailwindCSS, shadcn/ui | Charts via Recharts/Visx. |
| Auth (V2) | FastAPI + JWT, or managed (Clerk / Supabase Auth) | Decide at V2. |
| LLM (Later) | **Anthropic API (Claude)** behind FastAPI | Use latest Claude models. |

### 5.2 Database decision: PostgreSQL (resolved)

**Chosen: PostgreSQL over MongoDB.** The two hardest problems in this project map directly onto Postgres features:

- **Fuzzy identity/name matching** (core to search): the `pg_trgm` extension provides trigram similarity search — exactly what "find my name across providers despite spelling/formatting variation" needs, without adding a separate search engine.
- **Heterogeneous provider data:** use **normalised relational columns** for fields every provider shares (name, time, date, discipline, distance) **plus a `JSONB` column** for provider-specific extras. This gives structure where we want it and flexibility where we need it — the main thing Mongo would offer, but without losing relational integrity or `pg_trgm`.
- **Time-series analysis:** SQL **window functions** make "finish time over time within a discipline" straightforward.
- **Relational matching:** `athlete → claimed_result → result → event → provider` is naturally relational.

> MongoDB would only win if the data were truly schema-less and we didn't need fuzzy search or joins. Neither is true here.

### 5.3 Architecture

```
                 ┌─────────────────────────────────────────┐
                 │              Ingestion layer              │
                 │  (Python, run as scheduled/decoupled jobs)│
                 │                                           │
  race sites ───▶│  Provider scrapers (httpx/BS4/Playwright) │
  (scrape, MVP)  │        │                                  │
  provider APIs  │        ▼                                  │
  (feed, V1)     │  Normaliser → canonical records           │
                 └────────────────────┬──────────────────────┘
                                       │ upsert
                                       ▼
                 ┌─────────────────────────────────────────┐
                 │           PostgreSQL (canonical)          │
                 │  provider · event · result · athlete ·    │
                 │  claimed_result   (+ JSONB raw, pg_trgm)  │
                 └────────────────────┬──────────────────────┘
                                       │
                                       ▼
                 ┌─────────────────────────────────────────┐
                 │              FastAPI backend              │
                 │  /search · /results · /me/results ·       │
                 │  /analysis                                │
                 └────────────────────┬──────────────────────┘
                                       │ HTTP/JSON
                                       ▼
                 ┌─────────────────────────────────────────┐
                 │  Frontend — Next.js (V1; Streamlit in MVP)│
                 └─────────────────────────────────────────┘
```

> ngestion should be decoupled from the rest of the process. Scraping should run as scheduled / offline jobs that write to the DB *not* on-demand when a user searches. For MVP, "scheduled" can simply be a manually-run CLI script per provider; real scheduling (cron/worker) arrives in V2.

### 5.4 Canonical data model

This is the core normalisation decision (the answer to "what single schema do all providers map into?"). Based on the agreed rules: **chip time**, **each race's own age bucket**, **distances standardised to km**, **final results only (no splits)**.

**`provider`**
| column | type | notes |
|---|---|---|
| id | PK | |
| slug | text unique | e.g. `sporthive` |
| name | text | display name |
| base_url | text | |
| ingest_type | enum(`scrape`,`api`) | MVP: `scrape` |

**`event`** (a specific race occurrence)
| column | type | notes |
|---|---|---|
| id | PK | |
| provider_id | FK → provider | |
| external_id | text | provider's own event id, if any (used for idempotent upserts) |
| name | text | e.g. "London Marathon 2024" |
| discipline | enum(`running`,`cycling`,`swimming`,`triathlon`,`duathlon`) | |
| distance_label | text | **primary comparability key** — e.g. `10K`, `Marathon`, `Olympic`, `Ironman 70.3` |
| distance_km | numeric null | single-discipline only; **null for multi-sport** (see note) |
| event_date | date | |
| location | text null | |
| source_url | text | |
| raw | jsonb | original payload |
| scraped_at | timestamptz | |

**`result`** (one athlete's final result in one event)
| column | type | notes |
|---|---|---|
| id | PK | |
| event_id | FK → event | |
| athlete_name | text | as published; indexed with `pg_trgm` |
| gender | text null | as published |
| age_group | text null | **as the race published it** (e.g. `V40`, `35-39`, `Senior`) |
| chip_time_seconds | integer | **chip time**, stored as seconds (render as HH:MM:SS) |
| overall_rank | int null | |
| gender_rank | int null | |
| category_rank | int null | |
| finisher | bool | |
| raw | jsonb | original row |

**`athlete`** (MVP: single profile)
`id`, `display_name`

**`claimed_result`** (which results the user says are theirs)
`athlete_id` FK, `result_id` FK, `unique(athlete_id, result_id)`

> **Multi-sport note:** For triathlon/duathlon, a single `distance_km` is meaningless (an Olympic tri is 1.5km swim + 40km bike + 10km run). We therefore use **`distance_label` as the comparability key** for all disciplines, and only populate `distance_km` for single-discipline races. This keeps "standardise to km" honest without forcing a false number onto multi-leg events.

> **🟡 Open question (age as a bucket vs number):** We're storing the race's own age bucket (per your decision). That means two races using *different* bucketing schemes (e.g. `V40` vs `40-44`) aren't directly comparable, and we can't compute **age-grading** (a standard, powerful amateur-athletics metric) without actual age/DOB. Fine for MVP. **💡 Recommendation:** revisit in V1 — capture age/birth-year where available to unlock age-graded analysis.

### 5.5 Ingestion & scraping

- **MVP:** one scraper module per hand-picked provider, each implementing a common interface:
  - `discover()` → list of event URLs/ids for the configured races
  - `fetch(event)` → raw HTML/JSON
  - `parse(raw)` → list of canonical `event` + `result` records
  - `upsert()` → write to DB (idempotent on `provider_id + external_id`)
- Store **both** the normalised records **and** the `raw` JSONB payload, so re-parsing is possible without re-scraping.
- **Politeness/reliability:** respect `robots.txt`, rate-limit, set a real User-Agent, cache raw responses, fail soft per-record.
- **V1:** introduce an `api` ingest type and migrate priority providers to API feeds (see §7).

For MVP the providers are (decided after the §8 feasibility spike):
* **RaceBest** (https://racebest.com): ingested. Results are embedded as JSON in server-rendered pages.
* **UKResults** (https://www.ukresults.net): ingested. Static HTML, one page per race per year.
* RunThrough (https://results.runthrough.co.uk): scraper written but **user-run only**. robots.txt opts out of AI agents, and its data is excluded from future LLM features.
* Event Chip Timing (https://results.eventchiptiming.com): scraper written but **user-run only**. It's a RaceTec site with the same AI-agent opt-out as RunThrough, and both share one RaceTec base scraper.
* resultsbase.net: **blocked**. Results pages sit behind a Cloudflare Turnstile challenge. A stub scraper remains until access is granted.

### 5.6 Search & identity resolution

- Search inputs: **name** (required), optional **discipline, provider, race name, age group**.
- **Matching:** `pg_trgm` similarity on `athlete_name` + exact/filter on the structured fields, returning candidates ranked by a confidence score.
- User reviews candidates and **claims** the ones that are theirs → `claimed_result`.
- Claim data becomes training signal for smarter matching later (and LLM-assisted matching in the "Later" milestone).

### 5.7 Analysis engine (MVP)

- **Definition (agreed):** compare **headline results of the same discipline over a time series**.
- A **comparison group** = results sharing `(discipline, distance_label)` within the user's claimed set — e.g. all `running / 10K` results.
- MVP metrics per group:
  - **Finish time** (chip) over time.
  - **Pace** (min/km) for single-discipline events (derived from `chip_time_seconds` and `distance_km`).
  - Simple trend (improving/declining), personal best, most recent vs PB.
- Rendered as a **time-series chart** per comparison group.

> **💡 Recommendation:** Default the analysis view to the comparison group with the most claimed results, so the user sees something meaningful immediately.

### 5.8 API surface (FastAPI, MVP)

| Method | Path | Purpose |
|---|---|---|
| GET | `/search` | query params: name, discipline?, provider?, race?, age_group? → ranked candidate results (each result carries `time_source`: chip / gun / unspecified) |
| GET | `/results/{id}` | single result detail, with field sizes (overall / gender / category finishers) for "N of M" positions |
| GET | `/me/results` | the user's claimed results |
| POST | `/me/results` | claim a result (`result_id`) |
| DELETE | `/me/results/{id}` | unclaim |
| GET | `/analysis` | query param: discipline / comparison group → time-series data |
| GET | `/me/summary` | dashboard: totals, each comparison group's PB / latest / trend, recent results (V1) |

### 5.9 Frontend

> **✅ Decided (V1 frontend, 2026-11-09):** **Next.js 15 (App Router) + Tailwind v4 + shadcn/ui** in `web/`, with a clean and minimal look (neutral base, orange accent, light/dark). Pages are client components using TanStack Query against the FastAPI API. TypeScript types are generated from the API's OpenAPI schema, so Pydantic stays the source of truth. The scope of the first release is Streamlit parity plus a dashboard and a result detail page; Streamlit is then removed. See `docs/v1_plan.md`.

> **✅ Decided (MVP frontend):** **Streamlit** for the MVP — fastest path to a working data→analysis→UI loop, letting us focus on the hard problems (scraping, matching, analysis). The UI is throwaway; the **Next.js** frontend is built for V1 once the data layer is proven.

---

## 6. Non-functional & legal requirements

- **Legality of scraping:** check each provider's **ToS and robots.txt** before building a scraper. Prefer providers with APIs or permissive terms. Document the legal posture per provider.
- **Reliability:** scrapers break when sites change — keep them small, isolated per provider, and store raw payloads so parsing can be fixed without re-fetching.
- **Rate limiting & politeness:** throttle requests; identify the client honestly.
- **Data freshness:** results are final (immutable once published), so caching/periodic ingestion is low-risk.
- **Privacy:** results are published publicly by providers, but be mindful when (V2+) associating them with user accounts.
- **Deployment (MVP/V1 so far):** **local-only** — Postgres via Docker, FastAPI + the Next.js dev server run on the dev machine (Streamlit in the MVP). Hosting (e.g. Fly.io/Railway/Render + managed Postgres) is deferred to V1/V2.

---

## 7. Open questions & decisions log

### Decisions made
- **DB:** PostgreSQL (not MongoDB). §5.2
- **Data model:** chip time (seconds), race's own age bucket, km for single-discipline, `distance_label` as comparability key, no splits. §5.4
- **Analysis (MVP):** time series of headline results grouped by `(discipline, distance_label)`. §5.7
- **Ingestion:** decoupled/scheduled; scrape for MVP → APIs for V1. §5.5
- **MVP frontend:** Streamlit; Next.js for V1. §5.9
- **V1 frontend:** Next.js 15 + Tailwind + shadcn/ui, TanStack Query, OpenAPI-generated types; Streamlit retired at parity (V1 phase 1, done). §5.9
- **V1 phase 2 (2026-11-09):** the shift to API feeds is **deferred**. Phase 2 is instead a results-platform review with **access routes** (direct scrape / user-run / manual import / trace to source / permission / reject), a manual-import path (British Triathlon first), and 2–3 more route-1 providers. §8
- **V1 testing:** light automated checks: `npm run check` plus a Playwright smoke test run against the local DB as a throwaway test athlete. §6
- **MVP identity:** single hardcoded profile. §4
- **MVP deployment:** local-only (Docker Postgres + local FastAPI/Streamlit). §6
- **MVP providers:** RaceBest and UKResults are ingested. RunThrough and Event Chip Timing are user-run only (AI opt-out in robots.txt). resultsbase is blocked by a Cloudflare challenge. Never bypass bot checks or AI opt-outs. §5.5, §8

---

## 8. Provider feasibility spike

> Goal: for candidate results platforms, assess (1) **API vs scrape-only**, (2) **robots.txt / ToS** posture, (3) **static-HTML vs JS-rendered**, and recommend at least 2 MVP providers chosen by data-accessibility. **MVP spike complete (2026-11-08); extended into a UK triathlon-first review with access routes in V1 phase 2 (2026-11-09).**

**Access routes (V1 phase 2, 2026-11-09).** These replace the MVP's binary acceptance rule. Every platform gets one route, and the full review with evidence is in [`docs/providers/platform_review.md`](docs/providers/platform_review.md):
1. **Direct scrape**: robots.txt allows the results paths, including AI agents; terms silent/permissive; no bot check. Claude builds and runs it.
2. **User-run scrape**: AI agents opted out, generic bots allowed. Claude writes it without fetching results pages; the owner runs it.
3. **Manual import**: bot check or login. The owner saves the page or export in a normal browser, and `chipt-import` parses it. Personal use only.
4. **Trace to source**: aggregators and governing bodies. Use the original publisher's route.
5. **Ask permission / feed**: terms forbid copying or automated access; also required for V2/public use.
6. **Reject.**

Never bypass bot checks, CAPTCHAs or AI opt-outs. Data from AI-opted-out providers never goes to LLM features or test fixtures.

| Provider | Route | Reason |
|---|---|---|
| RaceBest | 1 (built) | No robots.txt. Terms silent. JSON embedded in pages |
| UKResults | 1 (built) | `Allow: /`. No terms published. Static HTML. Get permission before V2 |
| Eventrac | 1 (built) | Open robots.txt, silent terms. Hosted results are static HTML, whole field per page; redirects to organiser white-label domains |
| race-results.co.uk (SportSoft) | 1 (parked) | Open robots.txt, no terms. Static listing of organisers' PDF/Excel/HTML files |
| RunThrough, Event Chip Timing | 2 (built) | RaceTec; robots.txt opts out of AI agents, generic bots allowed |
| Net Timing, Race Timing Solutions, Timing Up North | 2 (cheap via `racetec.py`) | RaceTec; AI opt-out |
| Its Your Race, Timeoutdoors, Opentrack, Fetch Everyone, British Cycling | 2 (terms to check) | AI agents opted out |
| IRONMAN | 5 → official API (spike next) | `Claude-User` disallowed; terms forbid scraping and database use (as reported); official API portal with sign-up |
| British Triathlon | 3 (built: `chipt-import`) | Cloudflare challenge on every page; robots.txt otherwise allows results |
| resultsbase, UK Triathlon, Sports Timing Solutions | 3 | Turnstile / Cloudflare / JS+cookie gate (resultsbase also opts out `ClaudeBot`) |
| Castle Race Series | 4 | Organiser; links to Stuweb (≤2024) and British Triathlon |
| Stuweb, Sporthive (MYLAPS), Webscorer, World Triathlon | 5 | Terms forbid copying or automated collection |
| RaceResult, Sportsystems, Power of 10 / runbritain, Athlinks | 5 | robots.txt disallows results / login required / terms unverifiable |
| Let's Do This, SiEntries | 6 | Entry platforms, not results sources (and bot-checked) |

Per-provider detail is in `docs/providers/`.
