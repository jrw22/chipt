# Provider: British Triathlon (`britishtriathlon`)

- Site: https://www.britishtriathlon.org (the national governing body). It publishes results for sanctioned events, e.g. [Belvoir Castle Triathlon and Multisport Festival](https://www.britishtriathlon.org/events/results/belvoir-castle-triathlon-and-multisport-festival_17201) (id `17201`).
- Checked: 2026-11-09 (honest `ChiptBot` UA)
- **Route: 3, manual import.** The owner saves results pages in a normal browser, and `chipt-import britishtriathlon <files> --date …` parses them. **Built** (V1 phase 2 step 2); waiting for the first real saved race.

## Findings

- **robots.txt** allows `/events/results/` (`*` only disallows `/events/search` and `/events/search-on-map`). It has no AI-agent opt-out.
- **But every page returns a Cloudflare "Just a moment…" challenge (HTTP 403)** to a non-browser client. That includes the results page, the homepage, `/terms-and-conditions` and `/sitemap.xml`. Getting past it automatically would break CLAUDE.md's "never bypass bot checks" rule, so there is **no automated access**.
- **Terms of use:** couldn't be read (behind the challenge). Re-check them when the owner saves pages, and before any V2/public use.
- **Where the results come from:** British Triathlon seems to use different timing firms per event (e.g. Race Timing Systems for a Liverpool championship). Belvoir's organiser, Castle Race Series, links its ≤2024 results to Stuweb (route 5) and 2018–21 French races to Prolivesport. **Belvoir 2025–26 results appear only on British Triathlon**, so tracing back to the source doesn't help for those years.

## Manual import (built)

**How the page works:** an event's results page (e.g. `…_17201`) has a **Result** dropdown with one entry per race. Belvoir 2026 has 17: triathlon Super Sprint/Sprint/Sprint Plus/Starter/Standard/Middle, duathlon, aquabike and aquathlon Sprint/Standard(/Middle), plus junior TriStar/Youth races. The table is filled in by JavaScript, **50 rows per page**, with no option to show more. Columns: Pos, Athlete, Race Category (Open/Female), AG, Club, Overall (finish time), Stage 1, T1, Stage 2, T2, Stage 3, Race. **The page does not show the event date.**

**Owner workflow:**
1. Open the event's results page in your browser and pick your race in **Result**.
2. Save each 50-row page with File → Save Page As → **"Webpage, Complete"**. ("HTML Only" saves the page before the rows load, so you get an empty table.) Name the files `…-p1.html`, `…-p2.html`, and delete the `_files` folders.
3. Put them in `imports/BritishTriathlon/` (gitignored).
4. Check, then import:
   ```bash
   uv run chipt-import britishtriathlon imports/BritishTriathlon/belvoir-2026-*.html --date <Saturday YYYY-MM-DD> --dry-run
   uv run chipt-import britishtriathlon imports/BritishTriathlon/belvoir-2026-*.html --date <Saturday YYYY-MM-DD>
   ```

**What the importer does** (`src/chipt/ingest/providers/britishtriathlon.py`):
- **One event per race:** `external_id` = `<BT event id>:<race>` (e.g. `17201:triathlon-sprint`). Every saved page of a race lands in the same event, and re-imports are idempotent.
- **Labels:**
  - Triathlon: Super Sprint, Sprint, **Sprint Plus**, **Starter**, Standard → **Olympic**, Middle → **Middle Distance (70.3)**.
  - Duathlon is its own discipline (Middle → "Middle Distance", no 70.3).
  - Aquabike and aquathlon are filed under triathlon with an **"Aquabike "/"Aquathlon " prefix**, so they're never compared with triathlons.
  - Junior races are labelled "Tristar N" / "Youth".
- **Date:** `--date` gives it. If that's a Saturday, races named "… - Sunday" get the next day (and the reverse).
- **Fields:**
  - "Race Category" (Open/Female) is stored as published in `gender`, and AG is stored as published in `age_group`.
  - A non-numeric Pos (DNF/DSQ) with a time → `finisher = false`. Rows without a time are skipped.
  - Splits and club are kept in `raw` only.
- **Not yet verified on real rows:** the first real "Webpage, Complete" save may need small tweaks (e.g. relay teams, how DNFs appear).
- **Personal use only.** Ask British Triathlon for permission or a feed before V2/public use (see `platform_review.md`, outreach).
