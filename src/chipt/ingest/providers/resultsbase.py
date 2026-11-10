"""Results Base scraper: results.resultsbase.net (RaceTec platform), e.g. the Cambridge Half Marathon.

USER-RUN ONLY. results.resultsbase.net's robots.txt disallows AI crawlers and AI agents
(ClaudeBot, Claude-User, ...): it's the same RaceTec default file as RunThrough and Event Chip
Timing. So a person must run this, not an AI agent, and its data must not be sent to LLM
features or used as test fixtures. It was written without fetching any results page. All
parsing and pagination lives in the shared RaceTec base (`racetec.py`). See
docs/providers/resultsbase.md for the legal posture.

The other Results Base host, www.resultsbase.net (Sportstiming platform), is behind Cloudflare
Turnstile and is NOT scraped.

    uv run python -m chipt.ingest.providers.resultsbase list --match "cambridge"   # find race ids (RId)
    uv run python -m chipt.ingest.providers.resultsbase dump "<results url>"       # parse one race, no DB writes
    uv run chipt-ingest resultsbase                                              # ingest RACES into the DB
"""

from __future__ import annotations

from chipt.config import get_settings
from chipt.ingest.providers.racetec import RaceTecScraper, helper_cli
from chipt.schemas import ProviderIn

BASE_URL = get_settings().provider_resultsbase_results_url.rstrip("/")


class ResultsbaseScraper(RaceTecScraper):
    provider = ProviderIn(slug="resultsbase", name="Results Base", base_url=BASE_URL)
    BASE_URL = BASE_URL
    CLIENT_ID = "8"  # Results Base's RaceTec client id (CId)
    # Cambridge Half 2025 has 16,000+ finishers at 50 per page (~330 pages); leave headroom.
    MAX_RESULT_PAGES = 400

    # Hand-picked races: "RId", or "RId:EId" for one sub-event, plus "=<distance>" when the page
    # doesn't name it. `dump` lists a race's EIds. Add the same race from other years for a time series.
    RACES: list[str] = [
        "20708:1=Half Marathon",  # Cambridge Half Marathon 2025 (URL from the owner)
    ]


if __name__ == "__main__":
    helper_cli(ResultsbaseScraper)
