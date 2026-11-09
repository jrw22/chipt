# Provider: IRONMAN (`ironman`)

- Site: https://www.ironman.com (IRONMAN and IRONMAN 70.3, including UK races: Bolton, Wales, Swansea 70.3, …)
- Checked: 2026-11-09 (honest `ChiptBot` UA; robots.txt only)
- **Route: 5, official API.** Not scrapable by any automated route. **Status: API spike pending** (the owner signs up first).

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

## API spike (next, user-run pattern)

1. **Owner:**
   - Signs up at the API portal and gets a key.
   - **Reads the API terms** and checks two things: (a) personal, non-commercial use is allowed; (b) whether automated or AI-assisted access is restricted.
   - If either is a no, stop. IRONMAN stays route 5, and this doc records why.
2. **Owner shares** the endpoint shapes for one race (paths, parameters, auth header, pagination, field names; no result data).
3. **Agent writes** `src/chipt/ingest/providers/ironman.py`, the first `IngestType.api` provider:
   - the key in `.env` only (`PROVIDER_IRONMAN_API_KEY`), never committed or logged
   - HTTP through `PoliteClient`
   - a `probe` command that prints only the response **shape**, safe to paste back
4. **Owner runs** `probe`, the agent adjusts the parser, then the owner runs `uv run chipt-ingest ironman` twice (the counts must match).

**IRONMAN data is AI-opted-out:** it's excluded from LLM features and never used as test fixtures.
