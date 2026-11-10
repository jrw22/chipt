"""Run a provider scraper as an offline job (spec §5.3).

    uv run chipt-ingest resultsbase              # ingest the hand-picked races
    uv run chipt-ingest runthrough --url <URL>   # ingest one specific race page
    uv run chipt-ingest --list
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import logging

from chipt.config import get_settings
from chipt.ingest.base import BaseScraper, EventRef

# slug -> "module:ClassName"
PROVIDERS: dict[str, str] = {
    "resultsbase": "chipt.ingest.providers.resultsbase:ResultsbaseScraper",
    # runthrough: must be run by a person, not an AI agent (see docs/providers/runthrough.md)
    "runthrough": "chipt.ingest.providers.runthrough:RunThroughScraper",
    # eventchiptiming: must be run by a person, not an AI agent (see docs/providers/eventchiptiming.md)
    "eventchiptiming": "chipt.ingest.providers.eventchiptiming:EventChipTimingScraper",
    "racebest": "chipt.ingest.providers.racebest:RacebestScraper",
    "eventrac": "chipt.ingest.providers.eventrac:EventracScraper",
    "ukresults": "chipt.ingest.providers.ukresults:UkresultsScraper",
}


def load_scraper(slug: str) -> BaseScraper:
    module_name, cls_name = PROVIDERS[slug].split(":")
    return getattr(importlib.import_module(module_name), cls_name)()


def main() -> None:
    parser = argparse.ArgumentParser(description="Chipt ingestion CLI")
    parser.add_argument("provider", nargs="?", choices=sorted(PROVIDERS))
    parser.add_argument("--url", action="append", help="Ingest a specific race URL (repeatable)")
    parser.add_argument("--list", action="store_true", help="List configured providers")
    args = parser.parse_args()

    logging.basicConfig(level=get_settings().log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if args.list or not args.provider:
        print("\n".join(sorted(PROVIDERS)))
        return

    scraper = load_scraper(args.provider)
    refs = None
    if args.url:
        refs = [scraper.ref_from_url(u) if hasattr(scraper, "ref_from_url") else EventRef(url=u, external_id=u)
                for u in args.url]
    asyncio.run(scraper.run(refs))


if __name__ == "__main__":
    main()
