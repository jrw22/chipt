"""Common scraper interface (spec §5.5): discover() -> fetch() -> parse() -> upsert()."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from chipt.db.ingest_repo import upsert_parsed_event, upsert_provider
from chipt.db.session import get_engine
from chipt.ingest.http import PoliteClient
from chipt.schemas import ParsedEvent, ProviderIn

log = logging.getLogger(__name__)


@dataclass
class EventRef:
    """A pointer to one race on a provider's site, as returned by discover()."""

    url: str
    external_id: str
    meta: dict[str, Any] = field(default_factory=dict)


class BaseScraper(ABC):
    """Subclass once per provider, in its own module under chipt.ingest.providers.

    Subclasses set `provider` and implement discover/fetch/parse. `upsert` and
    `run` are shared. Use `self.http` for ALL network access so robots.txt,
    rate limiting, the User-Agent and the raw cache are applied.
    """

    provider: ProviderIn

    def __init__(self) -> None:
        self.http = PoliteClient(cache_namespace=self.provider.slug)

    @abstractmethod
    def discover(self) -> list[EventRef]:
        """Return refs for the configured (hand-picked) races."""

    @abstractmethod
    def fetch(self, ref: EventRef) -> Any:
        """Fetch the raw payload(s) for one race (HTML string, JSON, or a dict of pages)."""

    @abstractmethod
    def parse(self, ref: EventRef, raw: Any) -> list[ParsedEvent]:
        """Turn the raw payload into canonical records.

        One race page can yield several ParsedEvents (e.g. a 10K and a Half on
        the same day are separate events with different distance_labels).
        Must fail softly per row: skip and log unparseable rows, don't raise.
        """

    async def upsert(self, parsed: list[ParsedEvent]) -> None:
        async with get_engine().begin() as conn:
            provider_id = await upsert_provider(conn, self.provider)
            for pe in parsed:
                event_id, n = await upsert_parsed_event(conn, provider_id, pe)
                log.info("Upserted event %s (%s / %s): %d results",
                         event_id, pe.event.name, pe.event.distance_label, n)

    async def run(self, refs: list[EventRef] | None = None) -> None:
        refs = refs if refs is not None else self.discover()
        log.info("[%s] %d event(s) to ingest", self.provider.slug, len(refs))
        for ref in refs:
            try:
                parsed = self.parse(ref, self.fetch(ref))
            except Exception:  # fail soft per event
                log.exception("[%s] failed to fetch/parse %s", self.provider.slug, ref.url)
                continue
            if not parsed:
                log.warning("[%s] no events parsed from %s", self.provider.slug, ref.url)
                continue
            await self.upsert(parsed)
        self.http.close()
