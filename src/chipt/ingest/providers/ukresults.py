"""UKResults (https://www.ukresults.net) scraper.

UKResults is a long-running, family-run UK results service (with its timing arm
UKtimers.net) covering road, trail, fell and multisport races, mostly in
northern England. Results are **static HTML**, one page per race per year at
``/{year}/{slug}.html``, so `httpx` + BeautifulSoup is all we need.

Legal posture and quirks: see ``docs/providers/ukresults.md``.

Page shapes seen:
- Running: one ``table.sortable`` with header
  ``Pos | Num | M | F | Name | Cat | CatPos | Club | ChipTime | ChipPos | ... | GunTime``
  (``M``/``F`` hold the gender position; some races publish only ``Time``).
- Multisport (via Crazy Legs Events): one table split into sections by
  single-cell heading rows ("Tristart", "Youths", "Adults"), each followed by a
  ``Pos | Num | Name | Cat | Club | Run1 | T1 | Bike | T2 | Run2 | Total`` header.
  Each section is a separate race; we only ingest sections mapped in RACES
  (junior sections are skipped deliberately, see the provider doc).
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Any
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, Tag

from chipt.config import get_settings
from chipt.ingest.base import BaseScraper, EventRef
from chipt.ingest.normalise import (
    clean_name,
    infer_discipline,
    normalise_distance,
    parse_time_to_seconds,
    to_int,
)
from chipt.schemas import SINGLE_DISCIPLINES, EventIn, IngestType, ParsedEvent, ProviderIn, ResultIn

log = logging.getLogger(__name__)

# Suggested .env var: PROVIDER_UKRESULTS_BASE_URL (read if Settings grows the field).
BASE_URL = getattr(get_settings(), "provider_ukresults_base_url", "https://www.ukresults.net").rstrip("/")

# Hand-picked races. `name` keeps the series name stable across years (the
# site's own titles drift, e.g. "Guy Fawkes 10" vs "Guy Fawkes Ten"); the year
# is appended. `distance` is a hint for normalise_distance (titles such as
# "Guy Fawkes Ten" don't carry a parseable distance). `sections` maps a
# sectioned page's heading -> distance hint; unmapped sections are skipped.
RACES: list[dict[str, Any]] = [
    {"path": "2024/fawkes.html", "name": "Guy Fawkes 10", "distance": "10 mile"},
    {"path": "2025/fawkes.html", "name": "Guy Fawkes 10", "distance": "10 mile"},
    {"path": "2026/fawkes.html", "name": "Guy Fawkes 10", "distance": "10 mile"},
    {"path": "2025/13arches.html", "name": "Thirteen Arches Half Marathon", "distance": "Half Marathon"},
    {"path": "2026/13arches.html", "name": "Thirteen Arches Half Marathon", "distance": "Half Marathon"},
    # 2025 page is a single adult table; 2026 splits juniors and adults into sections.
    {"path": "2025/darleydumay.html", "name": "Darley Moor Sprint Duathlon (May)", "distance": "Sprint"},
    {"path": "2026/darleydumay.html", "name": "Darley Moor Sprint Duathlon (May)", "sections": {"Adults": "Sprint"}},
]

_DATE_RE = re.compile(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(\d{4})")
_CHIP_COLS = ("chiptime", "chip time", "nettime", "net time")
_TIME_COLS = ("time", "total", "finish time")
_GUN_COLS = ("guntime", "gun time")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "main"


def _cells(tr: Tag) -> list[str]:
    return [" ".join(td.get_text(" ").split()) for td in tr.find_all(["td", "th"])]


def _parse_date(*texts: str | None) -> date | None:
    for t in texts:
        m = _DATE_RE.search(t or "")
        if m:
            try:
                return datetime.strptime(" ".join(m.groups()), "%d %B %Y").date()
            except ValueError:
                continue
    return None


class UkresultsScraper(BaseScraper):
    provider = ProviderIn(slug="ukresults", name="UKResults", base_url=BASE_URL, ingest_type=IngestType.scrape)

    # -- discover / fetch ------------------------------------------------------ #
    def discover(self) -> list[EventRef]:
        return [self._ref(r["path"], r) for r in RACES]

    def _ref(self, path: str, meta: dict[str, Any]) -> EventRef:
        path = path.lstrip("/")
        return EventRef(url=f"{BASE_URL}/{path}", external_id=path.removesuffix(".html"), meta=meta)

    def ref_from_url(self, url: str) -> EventRef:
        path = urlsplit(url).path.lstrip("/")
        if not re.fullmatch(r"\d{4}/[\w-]+\.html", path):
            raise ValueError(f"Not a UKResults race results URL: {url}")
        known = next((r for r in RACES if r["path"] == path), {"path": path})
        return self._ref(path, known)

    def fetch(self, ref: EventRef) -> str:
        return self.http.get(ref.url)

    # -- parse ----------------------------------------------------------------- #
    def parse(self, ref: EventRef, raw: str) -> list[ParsedEvent]:
        soup = BeautifulSoup(raw, "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        headings = [" ".join(h.get_text(" ").split()) for h in soup.find_all(["h1", "h2", "h3"])]
        heading = next((h for h in headings if "," in h), headings[0] if headings else title)
        event_date = _parse_date(*headings, title)
        if not event_date:
            log.warning("[ukresults] %s: no race date found; skipping page", ref.url)
            return []

        page_name, _, location = heading.partition(",")
        race_name = ref.meta.get("name") or page_name.strip()
        if str(event_date.year) not in race_name:
            race_name = f"{race_name} {event_date.year}"
        location = location.strip() or None
        discipline = infer_discipline(title, heading)

        sections = self._sections(soup)
        if not sections:
            log.warning("[ukresults] %s: no results table found", ref.url)
            return []

        section_map: dict[str, str] | None = ref.meta.get("sections")
        multi = len(sections) > 1
        parsed: list[ParsedEvent] = []
        for section, header, rows in sections:
            if multi or section_map:
                hint = (section_map or {}).get(section) if section else None
                if hint is None:
                    log.info("[ukresults] %s: skipping section %r (%d rows) - not configured",
                             ref.external_id, section, len(rows))
                    continue
            else:
                hint = ref.meta.get("distance")

            label, km = normalise_distance(discipline, hint) if hint else (None, None)
            if not label:
                label, km = normalise_distance(discipline, heading, title)
            if not label:
                log.warning("[ukresults] %s: unknown distance for section %r; skipping", ref.external_id, section)
                continue
            if discipline not in SINGLE_DISCIPLINES:
                km = None

            results, skipped = self._parse_rows(ref, header, rows)
            log.info("[ukresults] %s %s / %s: %d results, %d skipped (no time / unparseable)",
                     ref.external_id, race_name, label, len(results), skipped)
            if not results:
                continue
            parsed.append(
                ParsedEvent(
                    event=EventIn(
                        external_id=f"{ref.external_id}:{_slug(label)}",
                        name=race_name,
                        discipline=discipline,
                        distance_label=label,
                        distance_km=km,
                        event_date=event_date,
                        location=location,
                        source_url=ref.url,
                        raw={"title": title, "page_name": page_name.strip(), "headings": headings,
                             "section": section, "columns": header, "distance_hint": hint},
                    ),
                    results=results,
                )
            )
        return parsed

    @staticmethod
    def _sections(soup: BeautifulSoup) -> list[tuple[str | None, list[str], list[list[str]]]]:
        """Split result tables into (section heading, header, data rows)."""
        out: list[tuple[str | None, list[str], list[list[str]]]] = []
        for table in soup.find_all("table"):
            section: str | None = None
            header: list[str] | None = None
            rows: list[list[str]] = []
            for tr in table.find_all("tr"):
                cells = _cells(tr)
                lowered = [c.lower() for c in cells]
                if "pos" in lowered and "name" in lowered:
                    if header and rows:
                        out.append((section, header, rows))
                    header, rows = cells, []
                elif len([c for c in cells if c]) == 1 and len(cells) <= 2:
                    if header and rows:
                        out.append((section, header, rows))
                        header, rows = None, []
                    section = next(c for c in cells if c)
                elif header and any(cells):
                    rows.append(cells)
            if header and rows:
                out.append((section, header, rows))
        return out

    def _parse_rows(self, ref: EventRef, header: list[str], rows: list[list[str]]) -> tuple[list[ResultIn], int]:
        lowered = [h.strip().lower() for h in header]

        def idx(*names: str) -> int | None:
            return next((lowered.index(n) for n in names if n in lowered), None)

        i_pos, i_name, i_cat = idx("pos"), idx("name"), idx("cat")
        i_catpos, i_m, i_f = idx("catpos"), idx("m"), idx("f")
        time_cols = [("ChipTime", idx(*_CHIP_COLS)), ("Time", idx(*_TIME_COLS)), ("GunTime", idx(*_GUN_COLS))]

        out: list[ResultIn] = []
        skipped = 0
        for row in rows:
            try:
                def cell(i: int | None) -> str | None:
                    return (row[i].strip() or None) if i is not None and i < len(row) else None

                raw_row: dict[str, Any] = {h or f"col{j}": (row[j] if j < len(row) else None)
                                           for j, h in enumerate(header)}
                name = cell(i_name)
                if not name:
                    skipped += 1
                    continue
                secs, source = None, None
                for src, i in time_cols:
                    secs = parse_time_to_seconds(cell(i))
                    if secs:
                        source = src
                        break
                if not secs:
                    skipped += 1  # DNF / DNS / no time
                    continue
                raw_row["_chipt_time_source"] = source
                if source == "GunTime":
                    raw_row["_chipt_note"] = "no chip time published; gun time used"

                gender, gender_rank = None, None
                if cell(i_m):
                    gender, gender_rank = "M", to_int(cell(i_m))
                elif cell(i_f):
                    gender, gender_rank = "F", to_int(cell(i_f))
                age_group = cell(i_cat)
                if gender is None and age_group:
                    # Multisport categories look like "F_50-54" / "F45-49" / "O_70-74" (O = open).
                    m = re.match(r"^([MF])(?=[_\d])", age_group)
                    gender = m.group(1) if m else None

                out.append(
                    ResultIn(
                        athlete_name=clean_name(name),
                        chip_time_seconds=secs,
                        gender=gender,
                        age_group=age_group,
                        overall_rank=to_int(cell(i_pos)),
                        gender_rank=gender_rank,
                        category_rank=to_int(cell(i_catpos)),
                        finisher=True,
                        raw=raw_row,
                    )
                )
            except Exception:  # fail soft per row
                skipped += 1
                log.warning("[ukresults] %s: could not parse row %r", ref.external_id, row, exc_info=True)
        return out, skipped
