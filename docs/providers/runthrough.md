# Provider: RunThrough (`runthrough`)

- Results site: https://results.runthrough.co.uk (a RaceTec-hosted results platform, https://www.racetec.net)
- Organiser site: https://www.runthrough.co.uk (operated by GW Active Ltd, trading as RunThrough Events)
- Status: **Scraper written but not run against the site; the project owner must run it by hand.** The owner chose option (a) below.
  `src/chipt/ingest/providers/runthrough.py` was written without fetching any results pages and
  has only been tested offline on synthetic HTML. A person (not an AI agent) runs it, using the
  honest `SCRAPER_USER_AGENT`. Data from this provider must be excluded from future LLM features.
  Workflow: `python -m chipt.ingest.providers.runthrough list` → pin RIds in `RACES` →
  `... dump <url>` to check parsing → `uv run chipt-ingest runthrough`.

## robots.txt

### `results.runthrough.co.uk/robots.txt` (checked 2026-11-08)

```
User-agent: GPTBot
User-agent: ClaudeBot
User-agent: CCBot
User-agent: Bytespider
User-agent: meta-externalagent
User-agent: cohere-ai
User-agent: cohere-training-data-crawler
User-agent: AI2Bot
User-agent: Diffbot
User-agent: ImagesiftBot
User-agent: OAI-SearchBot
User-agent: Claude-SearchBot
User-agent: PerplexityBot
User-agent: YouBot
User-agent: DuckAssistBot
User-agent: Amazonbot
User-agent: ChatGPT-User
User-agent: Claude-User
User-agent: Perplexity-User
User-agent: MistralAI-User
User-agent: Google-Extended
User-agent: Applebot-Extended
Disallow: /
```

- There is no `User-agent: *` group, so a generic crawler (for example, our `SCRAPER_USER_AGENT`,
  `ChiptBot/...`) is **technically allowed** on every path. `PoliteClient.allowed()` will return True.
- Every **AI crawler and AI agent** is explicitly disallowed from the whole site. That includes
  training crawlers (ClaudeBot, GPTBot, CCBot), search/retrieval bots, and the agents that act for a
  user (`Claude-User`, `ChatGPT-User`, `Perplexity-User`, `MistralAI-User`).

### `www.runthrough.co.uk/robots.txt`

`User-Agent: * / Allow: /`, with a sitemap. Results are not hosted on this site.

## Terms of use and privacy

- Terms & Conditions: https://www.runthrough.co.uk/terms-and-conditions. These are **event-entry**
  terms covering entry, cancellation, liability, photography/media consent, charity entries and conduct.
  They contain **no website terms of use** and no clause about scraping, automated access,
  reproducing content or results data.
- Privacy Policy: https://www.runthrough.co.uk/privacy-policy. Standard UK GDPR policy that covers
  cookies, marketing and facial recognition for photos. It says nothing about how published results
  are used or whether they may be reused.
- The results subdomain has no terms or privacy link of its own (only "©2026" and a RaceTec link).
  RaceTec's own terms were not reviewed.

## Legal posture

1. The ToS does **not** prohibit automated access, so on contract grounds scraping is permitted.
2. robots.txt allows a non-AI, honestly identified crawler such as ChiptBot. Running the Chipt
   scraper ourselves (a deterministic, rate-limited script with an honest UA) complies with the file
   as written.
3. **However**, the site operator has clearly opted out of AI agents, `Claude-User` and `ClaudeBot`
   included. The Claude Code agent asked to build this scraper has to fetch and inspect pages to do so,
   and its requests would be Claude-originated whatever UA string is sent. Sending a non-Claude UA to
   get past that would go against the operator's stated preference, and against the spirit of the
   CLAUDE.md rule to respect robots.txt. **The agent therefore stopped after fetching
   robots.txt, the results homepage once, and the organiser's T&C and privacy pages. It did not fetch
   any results pages.**
4. Results are personal data (names, gender and age category of private individuals) under UK GDPR.
   That is fine for MVP single-user use, but it matters for V2 (see the CLAUDE.md privacy note).

**Options for the project owner:**
- (a) Build and run the scraper yourself, without AI-agent fetching. The robots.txt allows ChiptBot,
  and the notes below give a starting point.
- (b) Email RunThrough (info@runthrough.co.uk) or RaceTec to ask for permission or a data feed.
  CLAUDE.md prefers providers with APIs or permissive terms, so this is the cleanest route.
- (c) Swap in a different second MVP provider whose robots.txt does not exclude AI agents.

## Technical notes (from the single homepage fetch)

- Platform: RaceTec results, ASP.NET WebForms (`__VIEWSTATE`, `<form method="post">`).
  Results are **server-rendered static HTML**, so `httpx` + BeautifulSoup should be enough and
  Playwright should not be needed.
- Homepage: "UPCOMING RACES" plus a paginated "ALL RACE RESULTS" list (86 pages of 20).
  - Pagination: `/StartPage.aspx?CId=16487&From=21&To=40` (CId 16487 = RunThrough client id).
  - Each race links to `results.aspx?CId=16487&RId=<race id>`. `RId` is the stable provider race id,
    so use `runthrough:<RId>` (plus the distance where one RId holds several) as `external_id`.
  - Race names often bundle several distances ("Battersea Park 5k, 10k & Half Marathon"). Each distance
    should become its own `ParsedEvent` with its own `distance_label`.
- Not yet verified: the layout of `results.aspx` (columns, chip vs gun time, how distances are split,
  results pagination, any JSON/XHR endpoints). Someone with permission to fetch has to check these.
- Quirk: some list entries show the current date rather than the race date (e.g. "Hertfordshire Half
  Marathon & 10k - 2nd November 2025" listed as 01/11/2026), so take `event_date` from the results
  page or the race name, not from the listing.

## Races chosen

None yet (blocked). Suggested candidates are recurring RunThrough races that appear in the listing
across several years, e.g. Hertfordshire Half Marathon & 10k, Battersea Park Running Festival,
Gainsborough 10k & Half Marathon.

## How to add a race (once the scraper exists)

Add the race's `RId` (from `results.aspx?CId=16487&RId=...`) to the hardcoded race list in
`src/chipt/ingest/providers/runthrough.py`, or run `uv run chipt-ingest runthrough --url <results url>`.
