# Provider: Event Chip Timing (`eventchiptiming`)

- Results site: https://results.eventchiptiming.com (RaceTec-hosted results platform, https://www.racetec.net)
- Company site: https://eventchiptiming.com (WordPress)
- Feasibility check: 2026-11-09
- **Status: working, run by the owner.** Grafman 2025 is ingested: the triathlon has 245 finishers + 6 DNFs, and the aquabike has 40.
  `src/chipt/ingest/providers/eventchiptiming.py` is a thin subclass of the shared RaceTec scraper
  (`racetec.py`, also used by [RunThrough](runthrough.md)). It was written without fetching any
  results pages and has only been tested offline on synthetic HTML. A person (not an AI agent) runs
  it, using the honest `SCRAPER_USER_AGENT`. **Data from this provider must be excluded from future
  LLM features.**

## Verdict

Feasible, but **user-run only**, the same as RunThrough. Nothing in the terms bans automated access,
and robots.txt allows a generic, honestly identified bot such as ChiptBot. But the results subdomain
explicitly opts out every AI crawler and AI agent, `Claude-User` included. So the Claude Code agent
did not fetch or inspect any results page. It wrote the scraper from the shared RaceTec code, and the
owner runs and checks it.

## robots.txt (fetched 2026-11-09)

### `results.eventchiptiming.com/robots.txt`

Identical to `results.runthrough.co.uk/robots.txt`. The following agents are all disallowed from `/`:
GPTBot, ClaudeBot, CCBot, Bytespider, meta-externalagent, cohere-ai, cohere-training-data-crawler,
AI2Bot, Diffbot, ImagesiftBot, OAI-SearchBot, Claude-SearchBot, PerplexityBot, YouBot, DuckAssistBot,
Amazonbot, ChatGPT-User, Claude-User, Perplexity-User, MistralAI-User, Google-Extended, Applebot-Extended.

- There is no `User-agent: *` group, so `ChiptBot/...` is **technically allowed** on every path, and
  `PoliteClient.allowed()` returns True.
- AI training crawlers, AI search bots and agents acting for a user are all opted out. This looks like
  a RaceTec platform default rather than something Event Chip Timing chose itself, but treat it as
  the operator's stated preference either way.

### `eventchiptiming.com/robots.txt`

WordPress/Yoast default: `User-agent: *` with an empty `Disallow:` (everything allowed), plus a
sitemap at `/sitemap_index.xml`. Results are not hosted here.

## Terms of use and privacy

- The company site's page sitemap lists no terms of use, legal or privacy page. Only `/results/`
  matched, so we found **no terms that prohibit scraping, automated access or reuse of results**.
- The results subdomain was not fetched, so any footer links it has were not reviewed. RaceTec's own
  terms were not reviewed either.
- Results are personal data (names, gender, age category of private individuals) under UK GDPR. That
  is fine for MVP single-user use, but it matters for V2 (see the CLAUDE.md privacy note).

## Legal posture

1. We found no ToS that prohibits automated access.
2. robots.txt allows a non-AI, honestly identified crawler, so a deterministic, rate-limited script
   that the owner runs complies with it as written.
3. The AI-agent opt-out means the Claude Code agent must not fetch results pages, including to
   develop the parser. The agent fetched only the two robots.txt files and the company site's
   sitemaps.
4. Cleanest route: email Event Chip Timing or RaceTec to ask for permission or a data feed
   (CLAUDE.md prefers providers with APIs or permissive terms).

## Technical notes (inferred, not verified)

- URL scheme matches RunThrough's RaceTec site:
  `results.aspx?CId=16202&RId=<race>&EId=<sub-event>`. `CId=16202` is Event Chip Timing's client id.
- `EId` most likely picks a sub-event within a race, e.g. one distance or wave. The scraper treats
  it as part of the race key: `external_id` is `<RId>.<EId>:<distance_label>`, or
  `<RId>:<distance_label>` when no EId is given.
- The race listing is assumed to be `StartPage.aspx?CId=16202&From=1&To=20`, as on RunThrough.
  Unverified. If `list` finds nothing, find RIds by browsing the site yourself.
- Event Chip Timing times running, triathlon and cycling events. Discipline comes from the race name
  (`infer_discipline`), so check it in `dump`.

## Races chosen

| Race spec | Race | Why |
|---|---|---|
| `10316:1=Middle Distance` | ATW Grafman Triathlon, 2025-06-01: middle distance triathlon | first race. The page doesn't name the distance, so it's pinned (confirmed by the owner) |
| `10316:2=Aquabike Middle Distance` | ATW Grafman, 2025-06-01: middle distance aquabike | same day, different sport. Pinned, because its own page doesn't link to itself |
| `8428:4=Middle Distance` | Grafman, 2026-06-07: middle distance triathlon | second year of the same race, which gives a time series |
| `8428:3=Aquabike Middle Distance` | Grafman, 2026-06-07: middle distance aquabike | second year of the aquabike |

Add the same race from other years for a time series.

## Results page layout (from the owner's `dump`, 2026-11-09)

- Results are paginated at **50 rows per page**. Grafman (RId 10316, EId 1) has 245 finishers over 5
  pages. The pager is not a `Page$N` postback; the shared pager detector handles it.
- Rows with a time but **an empty position are DNFs** (confirmed by the owner) and are stored with
  `finisher = false`. Grafman has 6, and the analysis excludes them.
- Headers: `Pos, Name, Name, Gun Time, Gun Time, Cat Pos (Gen Pos), Category, Gender, Club, Team,
  Start, Swim, T1, Cycle, T2, Run`.
  - **There is no chip time.** Gun time is stored, and `raw._time_source = "gun"` records that.
  - `Name` and `Gun Time` each appear twice. Each field takes the first non-empty copy per row.
  - `Cat Pos (Gen Pos)` holds both ranks, e.g. `3 (12)`, split into `category_rank` / `gender_rank`.
  - The splits (Swim, T1, Cycle, T2, Run) are out of MVP scope and kept only in `raw`.
- Sub-event links: EId 1 = "Results" (the triathlon), EId 2 = "Middle Distance Aquabike".
- The race name has no distance in it, so it is pinned in `RACES` (`=Middle Distance`).
- Aquabike is filed under `triathlon` but gets its own labels (`Aquabike Middle Distance (70.3)`),
  so it is never compared with the triathlon.

## Owner workflow

```bash
uv run python -m chipt.ingest.providers.eventchiptiming list --match "10k"   # find race ids (RId)
uv run python -m chipt.ingest.providers.eventchiptiming dump \
  "https://results.eventchiptiming.com/results.aspx?CId=16202&RId=10316&EId=1"   # check parsing, no DB writes
uv run chipt-ingest eventchiptiming                                            # ingest RACES
```

`dump` prints the header mapping, any unmapped columns and the race's other sub-events (EIds). If a
column is mapped wrongly or not at all, add its header text to `COLUMN_SYNONYMS` in `racetec.py`.
That change applies to RunThrough too.

## How to add a race

Add `"RId"` or `"RId:EId"` to `RACES` (one string per entry, each followed by a comma), plus `"=<distance>"` (e.g. `"=Middle Distance"`, `"=10k"`)
when the race name doesn't state the distance. The pinned distance also applies to `dump` and `--url` in `src/chipt/ingest/providers/eventchiptiming.py`, or run
`uv run chipt-ingest eventchiptiming --url <results url>`.
