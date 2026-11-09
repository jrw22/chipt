"""Results Base (https://www.resultsbase.net) scraper — BLOCKED, not implemented.

Status (feasibility spike, 2026-11-08): every event results page
(``/event/{id}/results``) returns a Cloudflare Turnstile "Verify you're human"
interstitial to non-browser clients, and the JSON event-search endpoint the
site's own pages call (``/General/EventList/SearchEvents``) returns 404 outside
a browser session. Bypassing a CAPTCHA/bot check is not an acceptable way to
get data under our scraping policy (CLAUDE.md), so this scraper deliberately
ingests nothing. See ``docs/providers/resultsbase.md`` for the full write-up and
the options for unblocking (asking Results Base for permission or a feed, or
manual export).

This module exists so ``chipt-ingest resultsbase`` runs without crashing
and explains why it did nothing. ``CANDIDATE_RACES`` records the races
hand-picked for when access is granted. They were chosen because the same race
appears across several years, which gives the time-series analysis something
to show.
"""

from __future__ import annotations

import logging
from typing import Any

from chipt.ingest.base import BaseScraper, EventRef
from chipt.schemas import IngestType, ParsedEvent, ProviderIn

log = logging.getLogger(__name__)

BASE_URL = "https://www.resultsbase.net"

# Hand-picked for when access is available (event ids found via public web search).
# Woodcote 10k across three years = a meaningful running/10K time series.
CANDIDATE_RACES: list[dict[str, Any]] = [
    {"event_id": "4708", "name": "Woodcote 10k 2019"},
    {"event_id": "5236", "name": "Woodcote 10k 2020"},
    {"event_id": "5646", "name": "Woodcote 10k 2022"},
    {"event_id": "6096", "name": "Richmond Spring Riverside 10K Run 2022"},
]

BLOCKED_REASON = (
    "resultsbase.net results pages are behind a Cloudflare Turnstile human-verification "
    "challenge; automated ingestion is disabled (see docs/providers/resultsbase.md)."
)


class ResultsbaseScraper(BaseScraper):
    provider = ProviderIn(
        slug="resultsbase",
        name="Results Base",
        base_url=BASE_URL,
        ingest_type=IngestType.scrape,
    )

    def discover(self) -> list[EventRef]:
        log.warning("[resultsbase] %s", BLOCKED_REASON)
        return []

    def ref_from_url(self, url: str) -> EventRef:
        log.warning("[resultsbase] ignoring --url %s: %s", url, BLOCKED_REASON)
        return EventRef(url=url, external_id=url, meta={"blocked": True})

    def fetch(self, ref: EventRef) -> Any:
        raise NotImplementedError(BLOCKED_REASON)

    def parse(self, ref: EventRef, raw: Any) -> list[ParsedEvent]:
        raise NotImplementedError(BLOCKED_REASON)
