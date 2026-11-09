# Provider: Results Base (`resultsbase`)

- Site: https://www.resultsbase.net (Results Base Ltd, Newport Pagnell, UK; Co. Reg. 8980122)
- Platform: white-label of the Sportstiming (sportstiming.dk) platform
- Feasibility spike: 2026-11-08
- **Status: BLOCKED. No data is ingested.** `src/chipt/ingest/providers/resultsbase.py` is a stub that logs why and returns no events.

## Update (2026-11-09, V1 phase 2 review)

robots.txt now also disallows `ClaudeBot` and `GPTBot` site-wide, so resultsbase data must stay out of LLM features. Its route is now **3, manual import** (owner-saved pages), alongside asking permission. See `platform_review.md`.

## Verdict

Legally the site is permissive (robots.txt allows `/event/*/results`, and there are no terms of use that ban automated access). Technically it blocks us: every results page sits behind a **Cloudflare Turnstile "Verify you're human" challenge**. That is a deliberate anti-bot control. Getting past it (solving or automating the CAPTCHA, reusing browser cookies, spoofing a browser User-Agent) would break the spirit of our scraping policy. So we don't scrape this site.

## robots.txt (fetched 2026-11-08)

`User-agent: *` disallows:
`/event/*/registration/*`, `/results/certificate/*`, `/diplom/*`, `/diplomabg.aspx`,
`/event/*/embedtabs/*`, `/event/*/embed/*`, `/event/*/app/*`, `/api/*`, `/profile/*`.

So `/event/{id}/results` is **allowed** for generic agents, and `/api/*` is **off-limits**.

Several named bots are disallowed from the whole site (SemrushBot, AhrefsBot, GPTBot, ClaudeBot, Bytespider, Amazonbot, meta-externalagent and others). The operator clearly doesn't want AI or SEO crawlers. Our agent (`ChiptBot`) isn't on that list, but this is a signal to weigh.

## Terms / privacy

- There is no Terms of Use page (`/terms`, `/termsandconditions`, `/page/terms` all 404). The footer links only to
  [Privacy policy](https://www.resultsbase.net/privacy), [Refund & Returns](https://www.resultsbase.net/refund-returns),
  [About](https://www.resultsbase.net/about) and [FAQ](https://www.resultsbase.net/page/faq).
- None of these pages mentions scraping, crawling, automated access or reuse of results.
- The privacy policy says results are published publicly ("participant list ... and results ... may appear online").
- Athletes can choose to be anonymised: their name then shows as "Name Witheld" (sic) in public results. Any future scraper should drop those rows.
- The FAQ says Results Base has its own "claim your result" feature in user profiles. This overlaps with Chipt's claim flow.

## Delivery mechanism (what we found)

| URL | Result for a non-browser client (honest UA) |
|---|---|
| `/`, `/results`, `/events`, `/privacy`, `/about`, `/page/faq` | 200, static HTML. The event lists are empty shells filled by JS. |
| `/General/EventList/SearchEvents?type=Finished&keyword=...` (the XHR the list pages call) | 404 HTML outside a browser session |
| `/event/{id}/results` (checked 4708, 5646) | 200, but the body is the Turnstile challenge page (`challenges.cloudflare.com/turnstile`, `/st_proxy_offload_captcha_verify`) |
| `/sitemap.xml` | 404 |

We found event ids through a public web search.

## Races picked (kept in the module for if/when access is granted)

| event id | race | why |
|---|---|---|
| 4708 | Woodcote 10k 2019 | same race across years: running/10K time series |
| 5236 | Woodcote 10k 2020 | " |
| 5646 | Woodcote 10k 2022 | " |
| 6096 | Richmond Spring Riverside 10K Run 2022 | a different race |

## Options to unblock

1. **Ask Results Base** (info@resultsbase.net) for permission and an allow-listed agent, or for a data feed or export. This is the preferred route and fits the V1 "API-based feeds" milestone.
2. **Manual export:** save a results page by hand in a normal browser and write an importer that parses local files. This is low volume and needs no automated access past the challenge. It still needs the provider's blessing before anything goes beyond personal use.
3. **Swap in another MVP provider** that has an API or permissive, unchallenged pages. The Sportstiming platform behind this site seems to be challenged everywhere, so its sister sites won't help either.

## How to add a race (once unblocked)

Add `{"event_id": ..., "name": ...}` to `CANDIDATE_RACES` in the module. Event ids come from the `/event/{id}/results` URL. Then implement `discover`/`fetch`/`parse` against the real results HTML, which nobody has seen yet because of the challenge.
