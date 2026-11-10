# Provider: Results Base (`resultsbase`)

- Site: https://www.resultsbase.net (Results Base Ltd, Newport Pagnell, UK; Co. Reg. 8980122)
- Platform: white-label of the Sportstiming (sportstiming.dk) platform
- Feasibility spike: 2026-11-08 (www host); RaceTec host checked 2026-11-10
- **Status: two hosts, two verdicts.**
  - **`results.resultsbase.net` (RaceTec): route 2, user-run scrape.** `src/chipt/ingest/providers/resultsbase.py` is a thin subclass of the shared RaceTec base. A person runs it, not an AI agent. **Its data must stay out of LLM features and test fixtures.** First race pinned: Cambridge Half Marathon 2025.
  - **`www.resultsbase.net` (Sportstiming): blocked** (Cloudflare Turnstile). Not scraped. The findings below are kept as history.

## RaceTec host: results.resultsbase.net (2026-11-10)

The owner found the Cambridge Half Marathon 2025 at
`https://results.resultsbase.net/Results.aspx?CId=8&RId=20708&EId=1`. That race has 16,000+ results at 50 per page (~330 pages), far too many to save by hand. The URL scheme (`Results.aspx?CId=&RId=&EId=`) is **RaceTec**, the platform behind RunThrough and Event Chip Timing. It's not the Sportstiming platform on the `www` host.

**robots.txt** (fetched 2026-11-10, honest `ChiptBot` UA): the same RaceTec default file as `results.runthrough.co.uk` and `results.eventchiptiming.com`. GPTBot, ClaudeBot, CCBot, Bytespider, meta-externalagent, cohere-ai, AI2Bot, Diffbot, OAI-SearchBot, Claude-SearchBot, PerplexityBot, YouBot, DuckAssistBot, Amazonbot, ChatGPT-User, **Claude-User**, Perplexity-User, MistralAI-User, Google-Extended and Applebot-Extended are all disallowed from `/`. There's **no `User-agent: *` group**, so an honest generic bot (`ChiptBot`) is allowed.

**Terms:** Results Base publishes no terms of use (checked 2026-11-08). The privacy policy says results are published publicly.

**What the agent did and didn't do:** it fetched robots.txt only. It did **not** fetch any results page, so it hasn't seen the HTML or checked for a bot challenge on this host. If the owner's run hits a challenge or a block, **stop** (no bypass). Then add your own result with **My results → Add a result**, and ask Results Base for an export.

**Owner workflow:**
```bash
uv run python -m chipt.ingest.providers.resultsbase dump "https://results.resultsbase.net/Results.aspx?CId=8&RId=20708&EId=1"
uv run python -m chipt.ingest.providers.resultsbase list --match "cambridge"   # other years' RIds
uv run chipt-ingest resultsbase      # ~330 pages, ~11 min at SCRAPER_RATE_LIMIT_SECONDS=2; cached afterwards
uv run chipt-ingest resultsbase      # again: the counts must match (idempotent)
```
- `dump` prints value-free column shapes, pager links and sub-events, which are safe to paste back. It fetches the whole race (all ~330 pages), so the ingest that follows reads from the cache. If a header is mapped wrongly, add its text to `COLUMN_SYNONYMS` in `racetec.py`.
- **Pagination:** the RaceTec base follows the pager automatically (GET links or ASP.NET postbacks). It logs progress every 25 pages. `ResultsbaseScraper.MAX_RESULT_PAGES = 400` (the default is 200 = 10,000 rows). If the cap is hit, the run logs a "TRUNCATED" warning.
- To add years, pin them in `RACES` as `"<RId>:<EId>=Half Marathon"`.
- **Config:** `PROVIDER_RESULTSBASE_RESULTS_URL` (default `https://results.resultsbase.net`). The old `PROVIDER_RESULTSBASE_BASE_URL` is no longer read, so you can delete it from `.env`.

## Sportstiming host: www.resultsbase.net (history)

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

## How to add a race
On the RaceTec host, add `"<RId>:<EId>=<distance>"` to `RACES` in the module. The Woodcote ids above are Sportstiming event ids on the www host and stay blocked.
