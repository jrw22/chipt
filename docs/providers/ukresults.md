# Provider: UKResults (`ukresults`)

- Site: https://www.ukresults.net. "UKresults and UKtimers", a family-run UK results service run by
  John Schofield since 1987, with a chip-timing arm at https://www.uktimers.net (Ipico chips).
  It mostly covers northern England (Yorkshire, Lancashire, Manchester), with results back to 1993.
- Covers road, trail, multi-terrain, fell, and **duathlon/triathlon/aquathlon** (the multisport
  results are often supplied by Crazy Legs Events).
- Module: `src/chipt/ingest/providers/ukresults.py` (`UkresultsScraper`)
- Status: **built and verified** on 2026-11-08.
- Suggested env var: `PROVIDER_UKRESULTS_BASE_URL=https://www.ukresults.net`. The module reads
  `Settings.provider_ukresults_base_url` if that field exists and otherwise falls back to the default.

## robots.txt (checked 2026-11-08)

```
User-agent: *
Allow: /

User-agent: bingbot
Disallow:
```

Everything is allowed, and there are no AI-agent opt-outs.

## Terms of use

The site publishes **no terms of use, copyright notice or privacy policy**. The pages checked were
the home page, the site map, `geninfo.html` (About), `indexinfo.html` (submission info) and
`racedata.html`. These describe a free service: organisers send results so that they can be
published, and the site asks organisers to "keep me and your runners informed".

### Legal posture: GREEN/AMBER (acceptable for MVP, ask before going further)

Nothing prohibits automated access or reuse, and robots.txt explicitly allows everything. In the
absence of terms, default UK copyright and database-right rules apply to the compiled results
tables. Low-volume, rate-limited, attributed personal use (the MVP) is low-risk. Any public or
multi-user use (V2) should get **explicit permission** from the site owner (contact details on
https://www.ukresults.net/contact.html). Results are personal data under UK GDPR, as with every
provider. **Junior sections are deliberately not ingested** (see quirks below).

## Delivery mechanism

Static HTML with **one page per race per year**: `/{year}/{slug}.html` (e.g. `2025/fawkes.html`).
The slug is usually reused every year, which makes time series easy. Yearly indexes are at
`/{year}/index.html`. `httpx` + BeautifulSoup is enough, and there is no JS. One request is made per
race, rate-limited by `PoliteClient`.

## Races chosen

| path | race | event (distance_label) | results | time column |
|---|---|---|---|---|
| 2024/fawkes.html | Guy Fawkes 10 2024 (Ripley) | running / 10 Mile | 841 | ChipTime |
| 2025/fawkes.html | Guy Fawkes 10 2025 (Pateley Bridge) | running / 10 Mile | 677 | ChipTime |
| 2026/fawkes.html | Guy Fawkes 10 2026 (Pateley Bridge) | running / 10 Mile | 533 | ChipTime |
| 2025/13arches.html | Thirteen Arches Half Marathon 2025 | running / Half Marathon | 153 | Time (only one published) |
| 2026/13arches.html | Thirteen Arches Half Marathon 2026 | running / Half Marathon | 153 | Time |
| 2025/darleydumay.html | Darley Moor Sprint Duathlon (May) 2025 | duathlon / Sprint (km = null) | 154 | Total |
| 2026/darleydumay.html | Darley Moor Sprint Duathlon (May) 2026 | duathlon / Sprint, "Adults" section only | 26 | Total |

That gives **7 events and 2537 results**. A second run left the counts unchanged (idempotent).
Spot checks against the pages matched exactly: Guy Fawkes 2026 winner David McKinnon 00:57:31 →
3451 s, and 2024 winner Edward Hobbs 00:54:04 → 3244 s.

### Expanded 2026-11-10

robots.txt re-checked first (`Allow: /`). Series come from the yearly indexes (`/{year}/index.html`). **70 events, 24,418 results:**

| Series (slug) | Years | Label |
|---|---|---|
| Guy Fawkes 10 (`fawkes`) | 2015–19, 2021–26 | running / 10 Mile |
| Thirteen Arches Half Marathon (`13arches`) | 2016–19, 2023–26 | Half Marathon |
| Dalby Dash 10K (`dalby`) | 2015–19, 2021–26 | 10K |
| Richmond Castle 10K (`richmond`) | 2015–19, 2021–26 | 10K |
| Haweswater Half Marathon (`hawes`) | 2015–17, 2019, 2022–26 | Half Marathon |
| Ian Hesketh Memorial Duathlon (`hesketh`), run 5K / bike 22K / run 5K | 2015–19, 2021–22, 2024–26 | duathlon / **Sprint** (hint) |
| Darley Moor Sprint Duathlon, May (`darleydumay`) | 2022–26 | duathlon / Sprint (2026: "Adults" section) |
| Darley Moor Sprint Duathlon, September (`darleydusep`) | 2021–25 | duathlon / Sprint (2025: "Adults" section; juniors skipped) |

**Older page formats** (fixed 2026-11-10):
- ≈2017–19 tables use **Forename + Surname** instead of Name, and "Cat/Pos" / "Pos/Cat".
- Hesketh's finish time column is **"Overall"** (DNFs show 00:00:00 and are skipped).
- Titles saying "Duathlon**s**" (plural) are now recognised as duathlon.

## Mapping and quirks

- **Running header:** `Pos | Num | M | F | Name | Cat | CatPos | Club | ChipTime | ChipPos | Pace |
  After… | GunTime`.
  - The `M` / `F` columns hold the **gender position**: whichever is filled gives gender and
    gender_rank.
  - `Cat` is the age group as published (`MS`, `M45`, `F70`). `CatPos` `"(001/038)"` →
    category_rank = 1.
  - Time precedence is `ChipTime` → `Time`/`Total` → `GunTime`. A gun-time fallback is noted in
    `raw._chipt_note`, and the column used is always recorded in `raw._chipt_time_source`.
- **The columns change between years.** For example, 2026 Fawkes adds `After Winner`, and Thirteen
  Arches publishes a single `Time` with no chip/gun split. Rows are mapped by header name, never by
  position.
- **Multisport pages** (Crazy Legs Events) put one table into sections: single-cell heading rows
  ("Tristart", "Tristar 1–3", "Youths", "Adults"), each followed by its own header
  `Pos | Num | Name | Cat | [CatPos] | Club | Run1 | T1 | Bike | T2 | Run2 | Total`.
  - Only the sections mapped in `RACES[...]["sections"]` are ingested. For now that is "Adults" →
    Sprint.
  - **Junior sections (Tristart/Tristar/Youths) are skipped on purpose**, because those are the
    names and results of children and are out of scope for an adult athlete hub. Each skipped
    section is logged.
  - Categories look like `F45-49`, `F_50-54` and `O_70-74` (`O` = open, i.e. not necessarily male).
    Gender is set only for an explicit `M`/`F` prefix and is null for `O`.
  - Names are often ALL CAPS, and `clean_name` title-cases them.
- **Titles drift across years** ("Guy Fawkes 10" vs "Guy Fawkes Ten"; "Thirteen Arches" vs "Radcliffe
  AC 13 Arches"), and some titles have no parseable distance ("Ten"). Each `RACES` entry therefore
  carries a stable series `name`, to which the year is appended, and a `distance` hint for
  `normalise_distance`. The site's own title is kept in `event.raw.page_name`.
- The **venue can move**: Guy Fawkes was at Ripley in 2024 and Pateley Bridge from 2025. `location`
  is taken from the page heading (the text after the first comma).
- The date comes from the heading `"1st November 2026"`.
- `external_id` = `{year}/{slug}:{distance-label-slug}`, e.g. `2025/fawkes:10-mile`.
- Rows with no parseable time (DNF/DNS) are skipped and counted in the log. None appeared in the
  chosen races.
- `Martin Brock (Walk)`: annotations in the name cell are kept as published.

## How to add a race

1. Browse `https://www.ukresults.net/{year}/index.html` and copy the race's page path, e.g.
   `2025/dalby.html`.
2. Add `{"path": "2025/dalby.html", "name": "Dalby Dash 10k", "distance": "10K"}` to `RACES` in
   `ukresults.py`. For sectioned multisport pages, use `"sections": {"Adults": "Sprint"}` instead of
   `distance`.
3. Run `uv run chipt-ingest ukresults`. For one page without editing the module, run
   `uv run chipt-ingest ukresults --url https://www.ukresults.net/2025/dalby.html`. In that case the
   distance is inferred from the title, and the race is skipped with a warning if the title has none.
4. Note that pages for races that haven't happened yet hold the **entry list** ("This will be the
   results page after the race"). Don't add them until results are posted.

## Candidates evaluated

See the full table in [racebest.md](racebest.md#candidate-providers-evaluated-second-provider-spike-2026-11-08).
In short:

| Candidate | Verdict |
|---|---|
| RaceBest | Accepted (provider 1) |
| UKResults | Accepted (provider 2): allow-all robots, no restrictive terms, static HTML, chip times |
| RaceResult, Sporthive | Rejected: results/data paths disallowed for `*` |
| Opentrack, Its Your Race, Timeoutdoors, Race Timing Solutions | Rejected: robots.txt opts out ClaudeBot/AI agents |
| Webscorer, Stuweb, RaceSplitter | Rejected: ToS prohibits scraping or reproduction (RaceSplitter is ambiguous, so kept as a fallback) |
| RaceTec, Sport Systems, Power of 10, SiEntries, Athlinks | Rejected: bot check / disallow-all / login / no results / unverified ToS |
