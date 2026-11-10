# Provider: Eventrac (`eventrac`)

- Site: https://www.eventrac.co.uk (UK events and entries platform; some events host their results on it)
- Checked: 2026-11-09 (review) and re-checked 2026-11-10 before building (honest `ChiptBot` UA)
- **Route: 1, direct scrape.** Built in `src/chipt/ingest/providers/eventrac.py`; ingested by the agent.

## Legal posture
- **robots.txt** (www.eventrac.co.uk, and identical on organiser white-label domains such as www.mccpromotions.com):
  - `*` disallows `/admin/`, `/api/`, `/login`, `/results/claim/`, `/results/unclaim/`, `/cdn/`, `/js/`, …
  - **`/e/<event>/results/…` and `/calendars/…` are allowed.**
  - No AI-agent opt-out.
- **Terms:** the participant terms (`/participant-terms`) have no clause on scraping or automated access. There are "Developers T&C's" (an API exists) that weren't needed.
- **Personal use.** Ask Eventrac (or use its developer API) before V2 or any public use.

## How the site works
- **Results index:** `/e/<slug>/results` lists every race of the event across years: date and time, race name, and a link `/e/<slug>/results/<id>`.
- **Results page:** one race, **the whole field in one static HTML table**. Columns are Position, First Name, Last Name, Gender, Time (+ an "Action" claim button).
- **Not everything is hosted:** many listed events link out to RaceResult, Sporthive, Active or Timing Up North instead. Those have their own routes and are ignored.
- **Redirects to white-label domains:** organisers can run Eventrac under their own domain, and Eventrac redirects results pages there (Lancing/Worthing → `www.mccpromotions.com`). `PoliteClient` now checks robots.txt and rate-limits **at every redirect hop** (it no longer lets httpx follow redirects silently).
- **Anonymised athletes:** athletes who hide their name show as blank name cells linking to an Eventrac profile, with no gender. **They're skipped by design** (they've opted out of being named, and a nameless row can't be found or claimed). Their positions stay as published.
- **Time source:** a bare "Time" column isn't labelled chip or gun, so it's stored as `unspecified`. A "Chip Time"/"Net Time" column would be stored as `chip`.

## Races ingested (none raced by the owner; picked for multi-year history)

| Event (slug) | Races | Years |
|---|---|---|
| Lancing 10K (`lancing-10k-3750`) | 10K | 2021–2026 (6) |
| Worthing Seafront 10K (`worthing-seafront-10k-3733`) | 10K | 2023–2026 (4) |
| Bedgebury Forest Half Marathon & 10K (`bedgebury-forest-half-marathon-and-10k-9257`) | Half Marathon + 10K (junior races skipped) | 2017–2026 (9 each; no 2020) |
| Hove Prom 10K (`hove-prom-10k-9600`) | 10K | 2015–2026 (10) |
| Reading Town 10K (`reading-town-10k-charity-3742`) | 10K | 2021–2026 |
| Sheffield City 10K (`sheffield-city-10k-charity-fun-run-3732`) | 10K | 2021–2026 |
| Sandown & Shanklin (IoW) Seafront 10K (`sandown-and-shanklin-i-o-w-seafront-10k-3738`) | 10K | 2021–2026 |
| Chelmsford Marathon & Half (`chelmsford-marathon-and-half-marathon-9483`) | Marathon + Half Marathon | 2016–2026 (10 yrs) |
| Tissington Trail Half Marathon (`tissington-trail-half-marathon-weekend-9222`) | Half Marathon | 2014–2026 (11 yrs) |
| Folkestone Rotary Half Marathon (`folkestone-rotary-half-marathon-9459`) | Half Marathon | 2012–2026 (14 yrs) |
| Eridge Park 10 Trail Challenge (`eridge-park-10-trail-challenge-9457`) | 10 Mile (via `DISTANCE_HINTS`: older races are named just "2021") | 2017–2026 (8) |
| Stebbing 10 (`stebbing-10-10036`) | 10 Mile | 2021–2026 |

**First ingest (2026-11-10):** 28 events and 6,312 results. **Expanded the same day to 113 events and 39,835 results** (47 × 10K, 42 × Half Marathon, 14 × 10 Mile, 10 × Marathon). Re-ingesting gives identical counts. `external_id` is Eventrac's results id.

## Running it
```bash
uv run python -m chipt.ingest.providers.eventrac list <slug>   # races on an event's index (* = skipped)
uv run chipt-ingest eventrac                                    # ingest EVENTS
```
**To add an event:** find a hosted one in the results listing (`/calendars/sport-events/results`, links that start `/e/…/results/…`) and add its slug to `EVENTS`. Races matching `SKIP_RACES` (junior, kids, fun run, canicross, walk, 1 mile) are left out.
