"""Import results files the owner saved in their own browser (route 3, manual import).

    uv run chipt-import britishtriathlon imports/BritishTriathlon/belvoir-2026-*.html --date 2026-07-18 --dry-run
    uv run chipt-import britishtriathlon imports/BritishTriathlon/belvoir-2026-*.html --date 2026-07-18
    uv run chipt-import --list

`--dry-run` parses and prints what would be imported without touching the database. Re-importing
the same files is idempotent (same upserts as `chipt-ingest`), and a race split over several
saved pages can be imported page by page.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import logging
from datetime import date

from chipt.config import get_settings
from chipt.ingest.file_import import FileImportScraper

# slug -> "module:ClassName" (FileImportScraper subclasses)
IMPORTERS: dict[str, str] = {
    "britishtriathlon": "chipt.ingest.providers.britishtriathlon:BritishTriathlonImporter",
}


def load_importer(slug: str, files: list[str], **options) -> FileImportScraper:
    module_name, cls_name = IMPORTERS[slug].split(":")
    return getattr(importlib.import_module(module_name), cls_name)(files, **options)


def _dry_run(importer: FileImportScraper) -> None:
    for ref in importer.discover():
        parsed = importer.parse(ref, importer.fetch(ref))
        print(f"\n# {ref.meta['file']}: {len(parsed)} event(s)")
        for pe in parsed:
            e = pe.event
            finishers = sum(r.finisher for r in pe.results)
            print(f"  == {e.name} | {e.discipline.value} / {e.distance_label} | {e.event_date} "
                  f"| {finishers} finishers, {len(pe.results) - finishers} DNF | external_id={e.external_id}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Import owner-saved results files (manual import)")
    ap.add_argument("provider", nargs="?", choices=sorted(IMPORTERS))
    ap.add_argument("files", nargs="*", help="Saved results files (HTML/JSON), e.g. imports/<provider>/*.html")
    ap.add_argument("--date", type=date.fromisoformat,
                    help="Event date (YYYY-MM-DD) when the saved page doesn't show it")
    ap.add_argument("--race", help="Which race the saved pages are (provider-specific, e.g. \"Triathlon Sprint\")")
    ap.add_argument("--dry-run", action="store_true", help="Parse and summarise only; no database writes")
    ap.add_argument("--list", action="store_true", help="List importers")
    args = ap.parse_args()

    logging.basicConfig(level=get_settings().log_level, format="%(levelname)s %(message)s")
    if args.list or not args.provider:
        print("\n".join(sorted(IMPORTERS)))
        return
    if not args.files:
        ap.error("give at least one saved results file")

    importer = load_importer(args.provider, args.files, event_date=args.date, race=args.race)
    if args.dry_run:
        _dry_run(importer)
    else:
        asyncio.run(importer.run())


if __name__ == "__main__":
    main()
