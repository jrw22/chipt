# Provider: British Triathlon (`britishtriathlon`)

- Site: https://www.britishtriathlon.org (the national governing body). It publishes results for sanctioned events, e.g. [Belvoir Castle Triathlon and Multisport Festival](https://www.britishtriathlon.org/events/results/belvoir-castle-triathlon-and-multisport-festival_17201) (id `17201`).
- Checked: 2026-11-09 (honest `ChiptBot` UA)
- **Route: 3, manual import.** The owner saves results pages in a normal browser, and `chipt-import britishtriathlon <file>` parses them. **Not built yet** (V1 phase 2 step 2).

## Findings

- **robots.txt** allows `/events/results/` (`*` only disallows `/events/search` and `/events/search-on-map`). It has no AI-agent opt-out.
- **But every page returns a Cloudflare "Just a moment…" challenge (HTTP 403)** to a non-browser client. That includes the results page, the homepage, `/terms-and-conditions` and `/sitemap.xml`. Getting past it automatically would break CLAUDE.md's "never bypass bot checks" rule, so there is **no automated access**.
- **Terms of use:** couldn't be read (behind the challenge). Re-check them when the owner saves pages, and before any V2/public use.
- **Where the results come from:** British Triathlon seems to use different timing firms per event (e.g. Race Timing Systems for a Liverpool championship). Belvoir's organiser, Castle Race Series, links its ≤2024 results to Stuweb (route 5) and 2018–21 French races to Prolivesport. **Belvoir 2025–26 results appear only on British Triathlon**, so tracing back to the source doesn't help for those years.

## Manual import (to build)

- **Owner action:** open each results page in a browser, use File → Save Page As (HTML only), and put the file in `imports/britishtriathlon/` (gitignored; it contains personal data).
- **The parser is built from the saved pages.** The event id comes from the page's canonical URL (`…_17201`), and each distance/sport on the page becomes its own `ParsedEvent`, with aquabike/aquathlon labels kept apart from triathlon.
- **Personal use only.** Ask British Triathlon for permission or a feed before V2/public use (see `platform_review.md`, outreach).
