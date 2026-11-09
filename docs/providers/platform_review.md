# UK results platform review (V1 phase 2)

- **Checked:** 2026-11-09, by the Claude Code agent, using the honest `ChiptBot/0.1` User-Agent at least 2 s apart.
- **Scope:** UK, triathlon-first. Running is covered more lightly. Cycling and swimming are only noted.
- **Method, per platform:**
  1. Fetch robots.txt first.
  2. If AI agents are opted out, read only the terms (no results pages).
  3. Stop at the first bot challenge.
  4. Otherwise fetch at most one results page to see how the data is delivered, and read the terms for scraping/reuse clauses.
- **Not legal advice.** Terms change, so re-check before building, and again before V2 or any public use.

## TL;DR

- **Triathlon is the hardest sport to get at automatically.** The big triathlon sources are all closed to automated access in some way:
  - British Triathlon, UK Triathlon and Let's Do This are behind Cloudflare.
  - Its Your Race and Timeoutdoors opt out of AI agents. IRONMAN disallows `Claude-User`, and its terms forbid scraping (official API instead).
  - Stuweb, Sporthive (MYLAPS) and World Triathlon have terms that forbid copying.
  - RaceResult and Sportsystems block their results paths in robots.txt.

  So triathlon coverage will come mostly from **manual import** (route 3, starting with British Triathlon), **user-run** RaceTec scrapers (route 2), and **asking permission** (route 5). Route 1 only covers it partly: some Eventrac events, and RaceBest/UKResults multisport.
- **Openly scrapeable (route 1) shortlist:**
  1. **Eventrac**: hosted results are static HTML, with the whole field on one page.
  2. **race-results.co.uk (SportSoft)**: a static listing of organisers' PDF/Excel/HTML files.
  3. **More races from RaceBest and UKResults**, which already work.
- **Cheapest wins overall:** three more **RaceTec** sites, **Net Timing**, **Race Timing Solutions** and **Timing Up North**. Each would be ~20 lines on the existing `racetec.py` base, but they're **user-run** (route 2) because they opt out of AI agents.
- **Two MVP verdicts changed:**
  - **Sporthive's** robots.txt now allows results (only live timing is blocked). It's still route 5, because the MYLAPS terms forbid downloading or copying data.
  - **resultsbase** now also opts out `ClaudeBot`/`GPTBot` (and it's still behind Turnstile).

## Access routes

| Route | When | Who runs it |
|---|---|---|
| **1. Direct scrape** | robots.txt allows the results paths, including AI agents; terms silent or permissive; no bot check | The Claude Code agent builds, tests and ingests it |
| **2. User-run scrape** | AI agents opted out but generic bots allowed; terms don't forbid | The agent writes it **without fetching results pages**; the owner runs it (the RaceTec pattern) |
| **3. Manual import** | Bot check or login, but the owner can view the page in a normal browser; personal use only | The owner saves the page or export; `chipt-import` parses the file |
| **4. Trace to source** | An aggregator or governing body republishes a timer's results | Find the original publisher and apply routes 1–3 there |
| **5. Ask permission / feed** | Terms forbid copying or automated access, or blocked with no source; anything for V2/public use | Outreach (template below) |
| **6. Reject** | Forbidden, with no alternative worth pursuing | n/a |

Data from route-2 providers, and from any provider whose robots.txt opts out of AI (whatever the route), **must never be sent to LLM features or used as test fixtures**.

## Assessment matrix

Abbreviations:
- **AI opt-out:** AI agents disallowed site-wide in robots.txt (e.g. `ClaudeBot`, `Claude-User`).
- **`*`:** the generic-bot rules.
- **CF:** Cloudflare challenge.

### Triathlon / multisport

| Platform | robots.txt | Terms | Bot protection | Delivery | Route |
|---|---|---|---|---|---|
| **British Triathlon** (britishtriathlon.org) | `*` allows `/events/results/`; no AI opt-out | Not readable (CF) | **CF "Just a moment…" on every page** (home, terms, sitemap: 403) | Unknown | **3 manual import** (+5 for anything beyond personal use) |
| **UK Triathlon** (uktriathlon.co.uk, organiser) | Not readable (CF on robots.txt itself) | Not readable | **CF** | PDF results per race (seen via search) | **3** (saved PDFs) / 5 |
| **Castle Race Series** (castleraceseries.com, organiser) | Open; no AI opt-out | n/a | None | Links out: Stuweb (≤2024), Prolivesport (France). 2025–26 Belvoir only on British Triathlon | **4 →** Stuweb (5) / British Triathlon (3) |
| **Stuweb** (stuweb.co.uk) | Open; no AI opt-out | **"shall not… reproduce… any part of the… site content"** | None | HTML | **5** |
| **Its Your Race** (itsyourrace.com) | **AI opt-out** (ClaudeBot, GPTBot, CCBot, anthropic-ai, Google-Extended) | Not reviewed | n/a | n/a | **2** (owner-run; terms to check first) |
| **Timeoutdoors** (timeoutdoors.com) | **AI opt-out** (same set) | Not reviewed | n/a | n/a | **2** (terms first) |
| **IRONMAN** (ironman.com) | **`Claude-User` / `ChatGPT-User`: `Disallow: /`**; `ClaudeBot`/`GPTBot`/`CCBot` only `/news/`; `*` `Allow: /` | **Claims exclusive IP over results and timing data; bars scraping with robots and putting content into databases/APIs** (as reported by [Slowtwitch](https://slowtwitch.com/triathlon/fyi-your-ironman-athlete-profile-including-photos-is-being-scraped-by-third-parties/); the agent can't read ironman.com). Has had aggregators shut down | n/a | **Official API**: [IRONMAN API Portal](https://developer.competitor.com) (Results / Events / Athlete Data; sign-up; portal also opts out AI agents) | **5 → official API** (see `ironman.md`) |
| **World Triathlon** (triathlon.org) | Not checked | **Forbids automated data collection without written permission** ([T&Cs](https://triathlon.org/terms-and-conditions)) | n/a | n/a | **5** |
| **Sports Timing Solutions** (sportstimingsolutions.co.uk) | No AI opt-out, but `*` disallows `/race-result/`, `/export_csv/`, `/rd.php` | No terms page found | **JS + cookie gate** on results ("One moment… Loading your results") | JS | **3** / 5 (gate + robots signal "no bots") |
| **Sportsystems** (events.sportsystems.co.uk) | **`Disallow: /`** on the results host | Has `/terms-of-use` (not needed) | None | n/a | **5** |
| **RaceResult** (my.raceresult.com) | `*` disallows `/*/*/list`, `/view`, `/details`, `/pdf` | n/a | None | JS + JSON | **5** |
| **Sporthive / MYLAPS** (sporthive.com) | Open except `/LiveTiming`, `/profile` (**changed** since the MVP spike) | **MYLAPS terms: users "may not download, copy, alter or publish any data… not placed [by them]"**; database rights claimed ([Apps terms](https://mylaps.com/wp-content/uploads/2025/07/Terms-of-Use-MYLAPS-Apps.pdf), [conditions of use](https://static.mylaps.com/media/MYLAPS%20conditions%20of%20use.pdf)) | None | JS app over a same-host JSON API (`/api/v0.2.3/eventresults/…`, with CSV endpoints) | **5** (technically easy; terms say no) |
| **Event Chip Timing** (RaceTec) | **AI opt-out** | No terms found | None | RaceTec HTML | **2** (built) |
| **RaceBest** (racebest.com) | None (404) | Silent | None | JSON in page | **1** (built) |
| **UKResults** (ukresults.net) | `Allow: /` | None published | None | Static HTML | **1** (built) |

### Running (lighter)

| Platform | robots.txt | Terms | Bot protection | Delivery | Route |
|---|---|---|---|---|---|
| **Eventrac** (eventrac.co.uk) | Open; no AI opt-out (disallows `/api/`, `/admin/`, `/results/claim/`) | Participant terms: no scraping/automated-access clause | None | **Hosted results: static HTML, whole field in one table** (Position, First/Last Name, Gender, Time). Some events link out to RaceResult / Sporthive / Timing Up North | **1 ✅ shortlist** |
| **race-results.co.uk** (SportSoft) | Open (disallows `/onlineentries/`) | None found | None | Static yearly listing → organisers' **PDF / Excel / HTML** files (northern England running, fell, duathlon) | **1 ✅ shortlist** (parser per format) |
| **Net Timing** (results.netiming.co.uk) | **AI opt-out**; no `*` group | n/a | n/a | RaceTec (`?CId=20008`) | **2** (cheap: `racetec.py`) |
| **Race Timing Solutions** (results.racetimingsolutions.co.uk) | **AI opt-out** | n/a | n/a | RaceTec | **2** (cheap) |
| **Timing Up North** (timingupnorthresults.co.uk) | **AI opt-out** | n/a | n/a | RaceTec (probably) | **2** (cheap) |
| **RunThrough** (RaceTec) | **AI opt-out** | Event T&Cs only | None | RaceTec | **2** (built) |
| **Opentrack** (opentrack.run) | **AI opt-out** | Not reviewed | n/a | n/a | **2** |
| **Fetch Everyone** (fetcheveryone.com) | **AI opt-out** | Not reviewed | n/a | n/a | **2** |
| **Power of 10 / runbritain** | None (404) | n/a | **Sign-in page with reCAPTCHA** (results need a login) | n/a | **5** |
| **resultsbase** (resultsbase.net) | `ClaudeBot`, `GPTBot` disallowed (**new** since the MVP); `*` allows results | None | **Turnstile** | n/a | **3** (data stays out of LLM features) |
| **Webscorer** | Open | Forbids scraping/copying (MVP spike) | None | n/a | **5** |
| **Athlinks** (US; ChronoTrack, used by EMIT UK) | Open | Terms page is a JS app, not verified | None | JS | **5** |
| **Let's Do This** (entries) | n/a (**CF on robots.txt**) | n/a | **CF** | Entries, not results | **6** |
| **SiEntries** | Open | n/a | Turnstile on forms | Entries, not results | **6** |

### Cycling / swimming (noted only)

| Platform | Finding | Route |
|---|---|---|
| **British Cycling** | **AI opt-out**; events search disallowed | 2 / 5 |
| **Swim England rankings** (swimmingresults.org) | Open, but many results paths disallowed (`/showmeets*`, `/splits/`, …) | 5 (revisit if swimming becomes a priority) |

## Recommendations

### Build next (phase 2 steps 2–4)

1. **Manual import route + British Triathlon** (route 3). This is the only way to get the British Triathlon-hosted results the owner cares about, including Belvoir 2025–26. Saved pages come from the owner's browser. The same route also unlocks resultsbase and saved UK Triathlon PDFs.
2. **Eventrac** (route 1).
   - **For:** static HTML, the whole field in one request, an open robots.txt, silent terms, and a broad UK event calendar.
   - **Against:** only *hosted* results count (outbound links go to platforms with their own routes), and the sample had no age category or chip/gun split. Check per event.
3. **race-results.co.uk** (route 1).
   - **For:** a simple static listing.
   - **Against:** results are organisers' files, so each format (HTML table, Excel, PDF) needs a parser. **Excel needs `openpyxl` and PDF needs `pdfplumber`, so both new dependencies need justifying.** Start with the HTML/Excel results and add PDF only if it's worth it.
4. **More races from RaceBest and UKResults**, especially multi-year triathlon and duathlon series.

### Cheap, but user-run (route 2)
- **Net Timing, Race Timing Solutions and Timing Up North** need only a `BASE_URL` and `CLIENT_ID` each on `racetec.py`, plus a provider doc. The owner runs `dump` and ingest.
- **Its Your Race and Timeoutdoors** are big for triathlon, but need their terms reviewed first, and they'd be built blind (no page fetching by the agent).
- **IRONMAN** isn't a scraping candidate at all (its terms forbid it). Its route is the **official API**, next up as a spike (see below).

### Ask permission (route 5): outreach list
0. **IRONMAN: official API.** The owner signs up at the [IRONMAN API Portal](https://developer.competitor.com) and reads the API terms (personal use? AI-assisted access?). If they're OK, IRONMAN becomes Chipt's first `api` provider, built on the user-run pattern. See `ironman.md`.
1. **British Triathlon**: results feed or API access. Highest triathlon value.
2. **Stuweb**, ideally together with **Castle Race Series**: Belvoir ≤2024.
3. **MYLAPS (Sporthive)**: they have an API. Ask for personal/non-commercial access.
4. **RaceResult**: they offer an official API to event organisers.
5. **Power of 10 / UK Athletics**: running rankings.

Draft email:

> Subject: Personal results-history tool: permission to use your published results
>
> Hi, I'm building Chipt, a personal (non-commercial, single-user) app that brings together my own race results from different timing platforms so I can track my progress over time. Your site publishes results for races I've taken part in. Would you be happy for me to fetch those public results pages (rate-limited, clearly identified as `ChiptBot`), or is there a feed, export or API you'd prefer I use? I'll only store final results, won't republish them, and will honour any conditions you set. Thanks, …

### Risk note
Race-results scraping can draw enforcement. HYROX sent cease-and-desist letters to at least eight results sites and apps in October 2026 ([the5krunner](https://the5krunner.com/2026/10/15/hyrox-cease-and-desist-scrapers/)). Chipt is personal and local, but it's another reason to get permission before V2 or any public use.

## Re-checking a platform
Re-run the checks before building any route-1 or route-2 scraper, because robots.txt and terms change. Two of the MVP verdicts above already have. Record the date and evidence in that provider's `docs/providers/<slug>.md`.
