# Provider: IRONMAN (`ironman`)

- Site: https://www.ironman.com (IRONMAN and IRONMAN 70.3, including UK races: Bolton, Wales, Swansea 70.3, …)
- Checked: 2026-11-09, re-checked 2026-11-10 (honest `ChiptBot` UA; robots.txt only)
- **Route: manual entry of your own results.** The official API portal lists no APIs (2026-11-10), and the site can't be scraped or imported. The owner types in their own result through **My results → Add a result**. Asking IRONMAN for a feed is optional (route 5).

## Findings

**robots.txt (www.ironman.com):**
- `User-agent: Claude-User` and `User-agent: ChatGPT-User`: **`Disallow: /`** (AI agents acting for a user, which is what the Claude Code agent is).
- `ClaudeBot`, `GPTBot`, `CCBot`: only `/news/` allowed.
- `User-agent: *`: `Allow: /`, with `Content-Signal: search=yes, ai-train=yes, use=reference`.

So the agent fetched nothing on ironman.com beyond robots.txt, and **did not read its terms directly**.

**Terms, as reported by [Slowtwitch](https://slowtwitch.com/triathlon/fyi-your-ironman-athlete-profile-including-photos-is-being-scraped-by-third-parties/):**
- IRONMAN asserts exclusive intellectual-property rights over race results, timing splits and photos.
- The terms bar scraping with robots and incorporating site content into a database or API.
- IRONMAN asked at least one aggregator (The Obsessed Triathlete) to shut down.

The owner should confirm these against the current terms in the ironman.com footer. Either way, **user-run scraping (route 2) and manual import (route 3) would also break these terms**, so neither is used.

**Official API:** the [IRONMAN API Portal](https://developer.competitor.com) (Competitor Public / Developer API) documents Results, Events and Athlete Data APIs, and needs sign-up. **The portal's robots.txt also opts out every AI agent** (`ClaudeBot`, `Claude-User`, `GPTBot`, `ChatGPT-User`, …), so the agent must not read the portal or its docs.

**Third-party datasets** (Coach Cox, Academic Torrents, Kaggle) are scraped copies with unclear licences. Not used.

## Official API: none available (2026-11-10)
The owner signed up at the IRONMAN API Portal. **No APIs are listed** in the portal after sign-up, so the planned API spike is dropped.

## Other options checked (2026-11-10)
- **robots.txt re-check:** unchanged. `Claude-User` is still disallowed site-wide (a Cloudflare-managed AI-agent block). The agent didn't fetch the results page (e.g. `/races/im703-weymouth/results`).
- **Trace to source (route 4):** no help. Per public announcements, IRONMAN Europe races are timed by **MYLAPS** and its local partners (MYLAPS terms forbid copying, route 5), and North American races by **Sportstats**.
- **Third-party copies:** ai-triathlon-result.teraren.com and endurance-data.com republish IRONMAN 70.3 Weymouth results (found via web search; not opened). These are scraped copies with no licence, and IRONMAN claims the rights. **Rejected.**
- **Not pursued** (owner's choice): a UK GDPR subject access request for the owner's own data, and an outreach email.

## Manual entry (built)
- **UI:** My results → **Add a result**. Fields: race, date, discipline, distance (canonical labels such as **Middle Distance (70.3)** and **Full Distance (140.6)**, so entries join the same comparison groups as scraped triathlons) and chip time. Optional: results platform ("IRONMAN"), link, age group, gender, positions and location.
- **API:** `POST /me/results/manual` (`repository.add_manual_result`). Each entry is its own event under the `manual` provider. Entering the same race again is idempotent. The detail view shows positions without "of N" field sizes.
- **AI opt-out:** entries with `source_platform` "IRONMAN" are flagged `raw.ai_opt_out = true`. Typing in your own result fetches nothing from ironman.com, but these entries stay out of future LLM features to be safe.
- Nothing from ironman.com is ever fetched, saved or parsed.
