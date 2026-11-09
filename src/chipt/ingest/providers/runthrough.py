"""RunThrough scraper: results.runthrough.co.uk (RaceTec platform).

USER-RUN ONLY. results.runthrough.co.uk's robots.txt disallows AI crawlers and AI agents
(ClaudeBot, Claude-User, ...), so this must be run by a person, not an AI agent, and its
data must not be sent to LLM features. All parsing lives in the shared RaceTec base; see
`racetec.py` for how it works and docs/providers/runthrough.md for the legal posture.

    uv run python -m chipt.ingest.providers.runthrough list --match "half"   # find race ids (RId)
    uv run python -m chipt.ingest.providers.runthrough dump "<results url>"  # parse one race, no DB writes
    uv run chipt-ingest runthrough                                         # ingest RACES into the DB
"""

from __future__ import annotations

from chipt.config import get_settings
from chipt.ingest.providers.racetec import RaceTecScraper, helper_cli
from chipt.schemas import ProviderIn

BASE_URL = get_settings().provider_runthrough_base_url.rstrip("/")


class RunThroughScraper(RaceTecScraper):
    provider = ProviderIn(slug="runthrough", name="RunThrough", base_url=BASE_URL)
    BASE_URL = BASE_URL
    CLIENT_ID = "16487"  # RunThrough's RaceTec client id (CId)

    # Hand-picked races: "RId", or "RId:EId" for one sub-event. Fill in after running `list`.
    RACES: list[str] = []
    # Used only when RACES is empty.
    RACE_NAME_PATTERNS = [r"hertfordshire half", r"battersea park", r"gainsborough"]


if __name__ == "__main__":
    helper_cli(RunThroughScraper)
