"""Event Chip Timing scraper: results.eventchiptiming.com (RaceTec platform).

USER-RUN ONLY. results.eventchiptiming.com's robots.txt disallows AI crawlers and AI agents
(ClaudeBot, Claude-User, ...), the same file as RunThrough's. So this must be run by a
person, not an AI agent, and its data must not be sent to LLM features. It was written
without fetching any results page. All parsing lives in the shared RaceTec base; see
`racetec.py` for how it works and docs/providers/eventchiptiming.md for the legal posture.

    uv run python -m chipt.ingest.providers.eventchiptiming list --match "10k"   # find race ids (RId)
    uv run python -m chipt.ingest.providers.eventchiptiming dump "<results url>" # parse one race, no DB writes
    uv run chipt-ingest eventchiptiming                                        # ingest RACES into the DB
"""

from __future__ import annotations

from chipt.config import get_settings
from chipt.ingest.providers.racetec import RaceTecScraper, helper_cli
from chipt.schemas import ProviderIn

BASE_URL = get_settings().provider_eventchiptiming_base_url.rstrip("/")


class EventChipTimingScraper(RaceTecScraper):
    provider = ProviderIn(slug="eventchiptiming", name="Event Chip Timing", base_url=BASE_URL)
    BASE_URL = BASE_URL
    CLIENT_ID = "16202"  # Event Chip Timing's RaceTec client id (CId)

    # Hand-picked races: "RId", or "RId:EId" for one sub-event. `dump` lists a race's EIds.
    # 10316:1 comes from the owner's example URL (results.aspx?CId=16202&RId=10316&EId=1);
    # race name/date unverified. Add the same race from other years for a time series.
    RACES: list[str] = ["10316:1"]


if __name__ == "__main__":
    helper_cli(EventChipTimingScraper)
