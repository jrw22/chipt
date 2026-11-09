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

    # Hand-picked races: "RId", or "RId:EId" for one sub-event, plus "=<distance>" when the page
    # doesn't name it. `dump` lists a race's EIds. Add the same race from other years for a time series.
    RACES: list[str] = [
        # ATW Grafman Triathlon, 2025-06-01 (confirmed by the owner).
        "10316:1=Middle Distance",  # middle distance triathlon; link text is just "Results"
        "10316:2",                  # middle distance aquabike; distance comes from the link text
    ]


if __name__ == "__main__":
    helper_cli(EventChipTimingScraper)
