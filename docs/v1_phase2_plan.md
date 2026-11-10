# V1 Phase 2: results-platform review, access routes and new providers

> Agreed with the owner on 2026-11-09. Step 1 output: [`providers/platform_review.md`](providers/platform_review.md). Finding: Belvoir's ≤2024 results are on Stuweb (route 5), and 2025–26 only on British Triathlon (route 3), so the timing-company trace doesn't help for recent years. Step 3's route-1 shortlist is **Eventrac** and **race-results.co.uk** (pending owner approval).

## IRONMAN (added 2026-11-09)
The owner asked about IRONMAN. It's **not scrapable**: `Claude-User` is disallowed, and the terms forbid scraping and database use (as reported). Its route is the **official IRONMAN API**. Order of work:
1. Platform review + IRONMAN docs (step 1).
2. ~~IRONMAN API spike~~: **dropped on 2026-11-10**, because the portal lists no APIs. It's replaced by **manual entry** (`feature/manual-entry`: "Add a result" + `POST /me/results/manual`). See [`providers/ironman.md`](providers/ironman.md).
3. Steps 2–4 below, unchanged.

## Context
V1 phase 1 (the Next.js UI) is complete (PRs #3–#7). The original phase 2 was "shift to API feeds". **The owner has deferred that.** Phase 2 now means:
1. An **in-depth review of UK results platforms**, with a recommended way to get each one's data.
2. **Building that out** for a few more providers and races.

The owner wants to explore British Triathlon, for example the [Belvoir Castle results page](https://www.britishtriathlon.org/events/results/belvoir-castle-triathlon-and-multisport-festival_17201).

**Feasibility checks so far (2026-11-09, honest `ChiptBot` UA):**
- **British Triathlon robots.txt** allows `/events/results/` and has no AI-agent opt-out.
- **But every page on britishtriathlon.org returns a Cloudflare "Just a moment…" challenge (403)**, including the homepage, the terms page and the sitemap. That's the same block as resultsbase, so automated access is out (CLAUDE.md: never bypass bot checks).
- **Belvoir's results are also linked by the organiser, Castle Race Series** ([race report](https://www.castleraceseries.com/news/belvoir-2026-race-report/), "See results"), probably on a timing company's site.
- **British Triathlon uses different timing firms per event** (e.g. a [Liverpool notice](https://www.britishtriathlon.org/news/provisional-results---british-triathlon-championships-liverpool_3384) names Race Timing Systems).
- **The current rules contradict each other.** Spec §8's acceptance rule rejects AI-opt-out providers, yet RunThrough and Event Chip Timing run as "user-run". Phase 2 replaces the binary accept/reject with explicit **access routes**.

**Owner decisions:**
- **Bot-blocked sites:** build a **manual import** route (the owner saves the page or CSV in their own browser, and Chipt parses the file) **and** trace events back to their timing company.
- **Review scope:** **UK, triathlon-first** (running covered more lightly; cycling and swimming only noted).
- **Build priority:** **openly scrapeable providers first** (2–3 new ones, plus more races). User-run candidates are listed for later.

## Access-route taxonomy (the review's core output)
| Route | When | Who runs it |
|---|---|---|
| **1. Direct scrape** | robots.txt allows the results paths, including AI agents; terms silent or permissive; no bot check | Built, tested and ingested by Claude (like RaceBest, UKResults) |
| **2. User-run scrape** | AI agents opted out, generic bots allowed, terms OK | Claude writes it without fetching results pages; the owner runs it (the RaceTec pattern) |
| **3. Manual import** | Bot check or login, but the owner can view the page in a browser; personal use | The owner saves the page or CSV; `chipt-import` parses the file |
| **4. Trace to source** | An aggregator or governing body (e.g. British Triathlon) republishes results | Find the timing company and apply routes 1–3 to it |
| **5. Ask permission / feed** | Terms prohibit, or blocked with no source; or anything for V2/public use | Outreach (email template in the review) |
| **6. Reject** | Terms prohibit and no alternative | n/a |

Data from route-2 providers, and from any provider whose robots.txt opts out of AI, stays out of LLM features (this applies to route 3 too).

## Work plan (one branch and PR per step)

### Step 1: platform review (`feature/v1-platform-review`), docs only, checkpoint with the owner
- **New `docs/providers/platform_review.md`:**
  - the taxonomy above
  - an assessment matrix
  - a recommended route per platform
  - a **build shortlist** (2–3 route-1 providers) for the owner to approve
  - an outreach list
- **Matrix columns:**
  - robots.txt (results paths; AI groups incl. `ClaudeBot` / `Claude-User`)
  - terms on scraping and reuse
  - bot protection
  - delivery: JSON / static HTML / JS / CSV export / API
  - fields: chip vs gun, splits, age category, DNF
  - sports
  - rough UK volume
  - date checked
- **Candidates, triathlon-first.** This is a starting list, expanded by web search; nothing is assumed until checked:
  - **Triathlon:** British Triathlon (blocked), Castle Race Series results / the Belvoir timing company, Race Timing Systems, Sports Timing Solutions, DB Max, Keep It Simple Timing, and other timers found for UK tri events
  - **Running:** Power of 10 / runbritain, Opentrack, SiEntries, Fetch Everyone, plus the existing six
  - **Cycling / swimming:** British Cycling, Swim England, noted only
  - Rejected platforms from spec §8 are re-stated with their route
- **Fetch discipline while researching:**
  - Fetch robots.txt first.
  - If AI agents are opted out, check only the terms pages; no results pages.
  - Stop at the first challenge.
  - Make one results-page fetch per platform at most, rate-limited, with the honest UA.
  - Research is done inline (no subagents).
- **Also:**
  - Rewrite spec §8: the acceptance rule becomes the routes, and the table gains a Route column.
  - Update the decisions log.
  - Redefine phase 2 in `docs/v1_plan.md` ("API feeds" moves to later).
  - Add `docs/providers/britishtriathlon.md`.
- **Checkpoint:** the owner approves the shortlist before step 3.

### Step 2: manual import route + British Triathlon (`feature/manual-import`)
- **`IngestType.manual`:**
  - Add it in `src/chipt/schemas.py`.
  - Add the enum value to `src/chipt/db/schema.sql` idempotently (`ALTER TYPE ingest_type ADD VALUE IF NOT EXISTS 'manual'`), so re-running `chipt-initdb` upgrades an existing DB.
- **`FileImportScraper`** (new `src/chipt/ingest/file_import.py`), a `BaseScraper` subclass (`src/chipt/ingest/base.py`):
  - `discover()` = the given file paths
  - `fetch()` = read the local file
  - `parse()` = the provider-specific parser
  - It reuses `upsert` / `run`, the normalise helpers (`src/chipt/ingest/normalise.py`) and the DNF/`finisher` and `time_source` conventions.
  - `external_id` comes from the page's canonical/og URL (BT's `_17201` id), falling back to a content hash.
  - The raw HTML is stored as usual.
- **CLI:** `uv run chipt-import <provider> <file>... [--distance <label>]`, a new script in `pyproject.toml`. It reuses `PROVIDERS`-style registration in `src/chipt/ingest/cli.py`.
- **`britishtriathlon` parser** (`src/chipt/ingest/providers/britishtriathlon.py`):
  - built from **owner-saved pages**: Belvoir 17201, plus other years or events if available
  - header-driven like `racetec.py` (`COLUMN_SYNONYMS`, `map_headers`, `parse_rows`, which can be reused or lifted into a shared helper)
  - handles multi-distance and multi-sport events (`distance_label`, aquabike/aquathlon labels via `normalise_distance`)
- **Saved files** go in `imports/` (gitignored: personal data).
- **resultsbase** gets the same route: its stub gains a file parser if the owner saves a page.
- **Owner action:** save the Belvoir page (File → Save Page As, HTML) into `imports/britishtriathlon/`.

### Step 3: 2–3 new route-1 providers (`feature/provider-<slug>` each)
- From the approved shortlist. Ideally that includes the timing company behind Belvoir/Castle Race Series, if it's route 1.
- Per provider:
  - `docs/providers/<slug>.md` (legal posture + technical notes)
  - an isolated module in `src/chipt/ingest/providers/`, registered in `cli.py`, with `PROVIDER_<SLUG>_BASE_URL` in `config.py` and `.env.example`
  - **multi-year races pinned**, so the time series has something to show
- Reuse the `PoliteClient` (`src/chipt/ingest/http.py`), and `racetec.py`'s pagination/header patterns where the platform matches.

### Step 4: more races for existing providers (`feature/more-races`)
- RaceBest / UKResults: more UK triathlon and duathlon races across several years.
- Event Chip Timing (Grafman, other years): the owner runs it.

## Verification
- **Review:** every matrix row has a check date, the evidence (robots excerpt / terms link / status code) and a route. The spec §8 and V1 plan edits are consistent.
- **Per provider / import:**
  - Run `chipt-ingest <slug>` (or `chipt-import`) twice; the event and result counts must be identical (idempotent).
  - Count checks in Postgres: finishers vs DNFs, `time_source`, and distance labels per event (counts only for opted-out data).
- **UI:**
  - Search a name from the new provider at `/find?provider=<slug>`.
  - Claim it as a temporary test athlete, check analysis, then remove the athlete (the step 4 test pattern; never the owner's claims).
- **Regression:** `cd web && npm run check` and `npm run test:e2e` pass. `chipt-initdb` re-runs cleanly on the existing DB, adding the `manual` enum.
- **Docs per PR:** changelog, project status, provider docs, CLAUDE.md (new CLI `chipt-import`, the `imports/` folder, routes summary), README (import commands).

## Constraints carried over
- Never bypass Cloudflare / CAPTCHAs / AI opt-outs: no browser UA, no reused cookies, no headless browser to get past a challenge.
- Manual-import files are saved by the owner in a normal browser, for personal use. V2/public use needs the provider's permission (noted in each provider doc).
- AI-opt-out data never goes to LLM features, and is never used as test fixtures.
