"""Route 3, manual import: parse results files the owner saved in their own browser.

Some providers block automated access (Cloudflare, bot checks, logins), but the owner can still
view their results in a normal browser. The owner saves the page or data file locally, and a
`FileImportScraper` subclass turns it into canonical records. **This code never touches the
network**: `discover()` is the list of files given on the command line, and `fetch()` reads one.

Everything else (`parse` conventions, idempotent `upsert`, `run`) is the normal scraper
interface in `chipt.ingest.base`, so imported results behave exactly like scraped ones.
Saved files live in `imports/` (gitignored: they contain personal data).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from chipt.ingest.base import BaseScraper, EventRef


class _NoNetwork:
    """Stands in for PoliteClient so an importer can't make a request by accident."""

    def get(self, *_: Any, **__: Any) -> str:
        raise RuntimeError("File importers must not use the network")

    post = get

    def close(self) -> None:
        pass


class FileImportScraper(BaseScraper):
    """Base for manual-import providers. Subclasses set `provider` and implement `parse`."""

    #: File suffixes this importer understands (checked before parsing).
    SUFFIXES: tuple[str, ...] = (".html", ".htm")

    def __init__(self, files: list[str | Path] | None = None, **options: Any) -> None:
        self.http = _NoNetwork()  # deliberately not BaseScraper.__init__: no PoliteClient
        self.files = [Path(f) for f in (files or [])]
        self.options = options  # importer-specific CLI options (e.g. event_date)

    def discover(self) -> list[EventRef]:
        refs = []
        for f in self.files:
            if f.suffix.lower() not in self.SUFFIXES:
                raise ValueError(f"{f}: expected one of {', '.join(self.SUFFIXES)}")
            data = f.read_bytes()
            refs.append(EventRef(
                url=f.resolve().as_uri(),
                external_id=hashlib.sha256(data).hexdigest()[:16],  # fallback; parsers prefer the page's own ids
                meta={"path": str(f), "file": f.name},
            ))
        return refs

    def fetch(self, ref: EventRef) -> str:
        return Path(ref.meta["path"]).read_text(encoding="utf-8", errors="replace")
