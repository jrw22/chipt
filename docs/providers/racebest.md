# Provider: RaceBest (`racebest`)

- Site: https://racebest.com (`www.racebest.com` redirects here). Operated by RaceBest Ltd
  (England & Wales company 8193734, Keighley). UK entry and results platform, strongest in Yorkshire
  and the North East.
- Covers road, trail, multi-terrain, fell, cross-country, track, **triathlon, aquathlon and duathlon**.
- Module: `src/chipt/ingest/providers/racebest.py` (`RacebestScraper`)
- Status: **built and verified** on 2026-11-08.
- Suggested env var: `PROVIDER_RACEBEST_BASE_URL=https://racebest.com`. The module reads
  `Settings.provider_racebest_base_url` if that field exists and otherwise falls back to the default.

## robots.txt (checked 2026-11-08)

`https://racebest.com/robots.txt` returns **404**, which means there is no robots.txt and so no
restrictions. There are no AI-agent opt-outs. `PoliteClient` treats a 404 as allow-all.

## Terms of use

The legal hub is https://racebest.com/legal, which links to these pages:
- Entrant T&Cs: https://racebest.com/legal/entrant-terms-and-conditions. They cover entry,
  refunds and liability. There is **no clause on automated access, scraping or reuse of site content**.
- Event Organiser T&Cs: https://racebest.com/legal/event-organiser-terms-and-conditions. Organisers
  must upload results "in a format suitable for publication" within 5 business days. The IP clause
  covers organiser material licensed to RaceBest and says nothing about third-party reuse.
- Privacy Policy: https://racebest.com/legal/privacy-policy. Results are published by the organiser,
  and RaceBest's lawful basis is legitimate interests.

There is no general website ToS.

### Legal posture: GREEN (acceptable for MVP)

Nothing prohibits automated access or reuse, robots.txt imposes no restrictions, and there are no
CAPTCHAs or bot checks. Results are personal data (name, club, category) under UK GDPR. That is fine
for single-user MVP use, but V2 multi-user "claiming" needs a privacy review. When this moves beyond
MVP, it would be courteous to ask admin@racebest.com for permission or a feed.

## Delivery mechanism

The pages are server-side rendered by Remix. Each results page, `GET /results/{code}`, embeds the
full race record and results table as JSON in `window.__remixContext.state.loaderData["routes/results.$url"]`:

```
race:        {url, name, date, startTime, location, distance, distanceUnits, courseType, series[], ...}
raceResults: {columns: [...], data: [[...]], published, lastUpdated}
```

That makes it effectively a structured JSON feed, and **one request per race**. No JS execution or
Playwright is needed. The results index `/results` embeds the latest 1000 races (`name, date,
courseType, distance, distanceUnits, url`), and each race's `series` lists its other years.

## Races chosen

| code | race | events (distance_label) | results |
|---|---|---|---|
| htsgw | Holmfirth 10K 2023 | 10K | 173 |
| qs29y | Holmfirth 10K 2024 | 10K | 154 |
| f7uw2 | Holmfirth 10K 2025 | 10K | 229 |
| x336r | Holmfirth 10K 2026 | 10K | 208 |
| qc7vz | Vale of York Half Marathon & 10K 2024 | Half Marathon / 10K | 893 / 254 |
| fcy5c | Vale of York Half Marathon & 10K 2025 | Half Marathon / 10K | 1057 / 293 |
| f629w | Harrogate Triathlon 2025 | Sprint / Super Sprint (triathlon, km = null) | 280 / 24 |
| wgayx | Harrogate Triathlon 2026 | Sprint / Super Sprint (Team Relay skipped) | 285 / 26 |

That gives **12 events and 3876 results**. A second run left the counts unchanged (idempotent).
Several athletes recur across years (e.g. Ben Jarvis: Holmfirth 2024 and 2026 plus Vale of York HM
2025; Reuben Hill: Harrogate Sprint 2025 and 2026), which makes them good demo profiles for claiming.

## Mapping and quirks

- **Columns vary per race and per year**, so rows are mapped by header name:
  - `Net Time` → chip time. `Gun Time` is used only if there is no net time, and that is noted in
    `raw._chipt_note`. Triathlon pages publish only `Time` (the total), which is used and recorded as
    `raw._chipt_time_source`.
  - `Gender Rank` `"1/157 (M)"` → gender_rank = 1, gender = `M`.
  - `Age Rank` `"1/16 (MV45)"` → category_rank = 1, age_group = `MV45`.
  - Holmfirth 2023 uses `10YR CAT` / `10YR CAT Rank` / `5YR CAT`, and there is no gender column. We
    take the 10-year category and leave gender null. Note that this makes the **age buckets differ
    across years for the same race** (2023 `MSEN`/`M40`, 2024+ `MV35`/`MV40`), as the spec's
    open question on age buckets predicted.
  - Triathlon `Name` is `"Name / AGEGROUP / CLUB"` (e.g. `Reuben Hill / O20-29 / RAF TRIATHLON`).
    The parts are split, and the age group comes from the middle part. `Category Rank`
    `"1/187 (OPEN)"` → category_rank.
- **Multiple distances on one page:** a `Distance` column (`HM`, `10K`), or a `[Contest]` suffix on
  `Position` (`"1/280 [Sprint]"`), splits the rows into separate `ParsedEvent`s. Their external_id is
  `{code}:{contest-slug}` (e.g. `fcy5c:hm`, `f629w:super-sprint`). On these pages `Position` is
  `"n/N"` within the contest.
- Contests whose name contains `relay` or `team` are skipped and logged, because they are not
  individual results.
- `distance_label` comes from `normalise_distance` on the contest name, or, for single-contest pages,
  on `distance` + `distanceUnits` (e.g. `10` + `Kilometres` → `10K`). `distance_km` is null for
  multi-sport.
- Discipline comes from `courseType` (`Triathlon`, `Duathlon`, `Road`, `Trail`, ...) via
  `infer_discipline`. Note that `Aquathlon` maps to `swimming` under the shared helper. No aquathlon
  is ingested yet, but this needs thought if one is added.
- Rows with no parseable time (DNF/DNS) are skipped and counted in the log. None appeared in the
  chosen races, because RaceBest seems to publish finishers only.
- Names go through `clean_name`, so all-caps names are title-cased.

## How to add a race

1. Find the race on https://racebest.com/results. The code is the last path segment, e.g.
   `/results/f7uw2`. A race's other years are listed in its page's `series` JSON.
2. Either add `{"code": "...", "name": "..."}` to `RACES` in `racebest.py` and run
   `uv run chipt-ingest racebest`, or run it once with
   `uv run chipt-ingest racebest --url https://racebest.com/results/<code>`.
3. Check the log for `could not determine distance` warnings. Free-text distances (e.g.
   `"2.4 - 13.1" Miles` with no `Distance` column) may need a contest column or a code tweak.

## Candidate providers evaluated (second-provider spike, 2026-11-08)

The spike replaced RunThrough (an AI-agent robots opt-out) and, after a scope change, Results Base
as well (Cloudflare Turnstile). Rule applied: reject any site whose robots.txt opts out
Claude/AI agents or disallows the results paths for `*`, any site whose ToS prohibits
scraping/reuse, and any site behind a bot check.

| Candidate | robots.txt | ToS | Delivery | Verdict |
|---|---|---|---|---|
| **RaceBest** (racebest.com) | none (404) | no scraping/reuse clause | SSR page with embedded JSON | **Accepted** |
| **UKResults** (ukresults.net) | `Allow: /` | none published | static HTML | **Accepted** (see `ukresults.md`) |
| RaceResult (my.raceresult.com) | `*` disallows `/*/*/list`, `/RRPublish`, … (the results data endpoints) | – | JSON XHR | Rejected: results paths disallowed |
| Sporthive / MYLAPS (sporthive.com) | site allows, but the data API `eventresults-api.speedhive.com` has `User-agent: * Disallow: /` | MYLAPS app terms silent | JS SPA + JSON API | Rejected: API disallowed for `*` |
| Opentrack (opentrack.run) | disallows ClaudeBot, anthropic-ai, Claude-Web | – | – | Rejected: AI opt-out |
| Its Your Race / Timeoutdoors | disallow ClaudeBot | – | – | Rejected: AI opt-out |
| Race Timing Solutions results | disallows ClaudeBot / Claude-User | – | – | Rejected: AI opt-out |
| Webscorer | permissive | "scraping … expressly prohibited" | HTML / keyed API | Rejected: ToS |
| Stuweb (stuweb.co.uk) | allows results, `Crawl-delay: 30` | "shall not … reproduce or create derivatives of … site content" | HTML | Rejected: ToS reuse clause |
| RaceSplitter (racesplitter.com) | allow-all | "not reproduce, duplicate, copy … any portion of the Service" (offset by "anyone may view and share your Content") | static HTML | Rejected (ambiguous ToS). Also hand-timed (no chip) and mostly non-UK. Fallback only |
| RaceTec results (racetecresults.com) | Cloudflare challenge on robots.txt itself | – | – | Rejected: bot check |
| Sport Systems (events.sportsystems.co.uk) | `User-agent: * Disallow: /` | – | – | Rejected |
| SiEntries | permissive | personal use only | entries only, no public results index | Rejected: no results |
| Power of 10 | – | – | now login-gated | Rejected |
| Chronotrack / Athlinks | permissive | ToS page JS-only (not verified) | SPA / auth redirect | Rejected: US-centric, unverified ToS |
| HS Sports chiptiming.co.uk | allow-all | – | results loaded by JS from a third party | Not pursued |
