"""British Triathlon results: manual import (route 3) of pages the owner saved in their browser.

britishtriathlon.org sits behind a Cloudflare challenge, so it is never fetched automatically
(see docs/providers/britishtriathlon.md). The owner opens an event's results page, picks a race
in the "Result" dropdown, and saves each 50-row page with File → Save Page As → "Webpage,
Complete" (which keeps the rows the site's JavaScript filled in). Then:

    uv run chipt-import britishtriathlon imports/BritishTriathlon/belvoir-2026-*.html --date 2026-07-18 --dry-run
    uv run chipt-import britishtriathlon imports/BritishTriathlon/belvoir-2026-*.html --date 2026-07-18

The table columns are: Pos, Athlete, Race Category (Open/Female), AG, Club, Overall (the finish
time), Stage 1, T1, Stage 2, T2, Stage 3, (blank), Race. Splits are kept in `raw` only (out of
MVP scope). Saved pages don't show the event date, so `--date` is required. If it's a Saturday
and a race is named "... - Sunday" (or the reverse), that race's date is shifted by a day.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from datetime import date, timedelta

from bs4 import BeautifulSoup, Tag

from chipt.ingest.base import EventRef
from chipt.ingest.file_import import FileImportScraper
from chipt.ingest.normalise import clean_name, normalise_distance, to_int
from chipt.ingest.providers.racetec import _norm_header, _text, cell_time_seconds
from chipt.schemas import Discipline, EventIn, IngestType, ParsedEvent, ProviderIn, ResultIn

log = logging.getLogger(__name__)

BASE_URL = "https://www.britishtriathlon.org"

# Normalised header text -> field. "Overall" is the finish TIME here (not a position).
COLUMNS: dict[str, str] = {
    "pos": "position",
    "position": "position",
    "athlete": "athlete_name",
    "name": "athlete_name",
    "race category": "race_category",
    "category": "race_category",
    "ag": "age_group",
    "age group": "age_group",
    "club": "club",
    "overall": "time",
    "time": "time",
    "race": "race",
}

_EVENT_ID = re.compile(r"_(\d+)/?$")
_DAY = re.compile(r"\b(saturday|sunday)\b", re.I)
_NON_FINISH = re.compile(r"^(dnf|dns|dsq|dq|rtd|ret|dnc|otl)$", re.I)

# Distance words in BT race names, longest first so "Sprint Plus" wins over "Sprint".
_DISTANCE_WORDS = ["super sprint", "sprint plus", "sprint", "starter", "standard", "olympic", "middle", "long", "full"]
_EXPLICIT_LABELS = {"sprint plus": "Sprint Plus", "starter": "Starter"}


def race_short_name(race: str) -> str:
    """'Triathlon Sprint - Saturday - Individual or Relay' -> 'Triathlon Sprint'."""
    return race.split(" - ")[0].strip()


def classify_race(race: str) -> tuple[Discipline, str] | None:
    """Map a BT race name to (discipline, distance_label). None if it can't be classified.

    Aquabike and aquathlon are filed under triathlon (multi-sport) but always carry their own
    label prefix, so they're never compared with a triathlon of the same distance.
    """
    short = race_short_name(race).lower()
    junior = re.search(r"tristar\s*\d|youth", short)
    if junior:
        return Discipline.triathlon, race_short_name(race).split(")")[0].strip("( ").title()  # e.g. "Tristar 1"
    if "duathlon" in short:
        discipline, prefix = Discipline.duathlon, ""
    elif "aquabike" in short:
        discipline, prefix = Discipline.triathlon, "Aquabike "
    elif "aquathlon" in short:
        discipline, prefix = Discipline.triathlon, "Aquathlon "
    elif "triathlon" in short:
        discipline, prefix = Discipline.triathlon, ""
    else:
        return None
    word = next((w for w in _DISTANCE_WORDS if w in short), None)
    if word is None:
        return None
    if word in _EXPLICIT_LABELS:
        label = _EXPLICIT_LABELS[word]
    else:
        hint = {"middle": "middle distance", "long": "full distance", "full": "full distance"}.get(word, word)
        label, _ = normalise_distance(discipline, hint)
        if label is None:
            return None
        label = label.removeprefix("Aquabike ")  # we add our own prefix below
        if discipline == Discipline.duathlon:
            label = re.sub(r"\s*\((?:70\.3|140\.6)\)", "", label)  # triathlon mileages don't apply
    return discipline, f"{prefix}{label}"


def race_date(base: date, race: str) -> date:
    """Shift a weekend date to the race's day: base Saturday + '... - Sunday' -> Sunday."""
    m = _DAY.search(race)
    if not m:
        return base
    want = 5 if m.group(1).lower() == "saturday" else 6  # Monday=0
    delta = want - base.weekday()
    return base + timedelta(days=delta) if abs(delta) == 1 else base


def _page_info(soup: BeautifulSoup) -> tuple[str | None, str, str | None]:
    """(BT event id, event name, page URL) from the page's og:url / og:title or <title>."""
    og_url = soup.find("meta", attrs={"property": "og:url"})
    url = (og_url.get("content") if og_url else "") or ""
    m = _EVENT_ID.search(url)
    og_title = soup.find("meta", attrs={"property": "og:title"})
    title = (og_title.get("content") if og_title else None) or (_text(soup.title) if soup.title else "")
    title = re.sub(r"\s*[–-]\s*British Triathlon\s*$", "", title)
    title = re.sub(r"\s+Results\s*$", "", title).strip()
    page_url = url.replace("http://", "https://", 1) if url else None
    return (m.group(1) if m else None), title or "British Triathlon event", page_url


def _selected_race(soup: BeautifulSoup) -> str | None:
    """The race picked in the "Result" dropdown, if the saved page recorded it."""
    sel = soup.find("select", attrs={"name": "result"})
    opt = sel.find("option", selected=True) if sel else None
    return _text(opt) if opt and opt.get("value") else None


def _results_rows(soup: BeautifulSoup) -> tuple[list[str], list[dict]]:
    table = soup.find("table", id="datatable-results") or soup.find("table")
    if not isinstance(table, Tag):
        return [], []
    headers = [_text(th) for th in table.find_all("th")]
    mapping = {i: COLUMNS[_norm_header(h)] for i, h in enumerate(headers) if _norm_header(h) in COLUMNS}
    rows = []
    body = table.find("tbody") or table
    for tr in body.find_all("tr"):
        cells = [_text(td) for td in tr.find_all("td")]
        if not cells or len(cells) < 3 or (len(cells) == 1 and "no data" in cells[0].lower()):
            continue
        row = {field: cells[i] for i, field in mapping.items() if i < len(cells)}
        row["_raw"] = {(headers[i] or f"col{i}"): c for i, c in enumerate(cells) if i < len(headers) or c}
        rows.append(row)
    return headers, rows


class BritishTriathlonImporter(FileImportScraper):
    provider = ProviderIn(slug="britishtriathlon", name="British Triathlon", base_url=BASE_URL,
                          ingest_type=IngestType.manual)

    def parse(self, ref: EventRef, raw: str) -> list[ParsedEvent]:
        soup = BeautifulSoup(raw, "html.parser")
        if soup.find(string=re.compile(r"just a moment", re.I)) and not soup.find("table"):
            log.error("%s is a Cloudflare challenge page, not results. Open the page in your browser "
                      "and save it again once the results show.", ref.meta["file"])
            return []
        bt_id, event_name, page_url = _page_info(soup)
        headers, rows = _results_rows(soup)
        if not rows:
            log.error("%s: the results table is empty. Save with 'Webpage, Complete' after the results "
                      "have loaded (HTML Only saves the page before they appear).", ref.meta["file"])
            return []
        base_date: date | None = self.options.get("event_date")
        if base_date is None:
            log.error("%s: saved British Triathlon pages don't show the event date; pass --date YYYY-MM-DD",
                      ref.meta["file"])
            return []

        fallback_race = _selected_race(soup) or ref.meta["file"]
        groups: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            groups[r.get("race") or fallback_race].append(r)

        events = []
        for race, group in groups.items():
            kind = classify_race(race)
            if kind is None:
                log.error("%s: can't tell the sport/distance of race %r; skipping %d rows",
                          ref.meta["file"], race, len(group))
                continue
            discipline, label = kind
            results, skipped = self._results(group)
            log.info("%s %s: %d results (%d DNF), %d rows skipped", ref.meta["file"], label,
                     len(results), sum(not r.finisher for r in results), skipped)
            if not results:
                continue
            short = race_short_name(race)
            key = re.sub(r"[^a-z0-9]+", "-", short.lower()).strip("-")
            events.append(ParsedEvent(
                event=EventIn(
                    external_id=f"{bt_id or ref.external_id}:{key}",
                    name=f"{event_name} — {short}",
                    discipline=discipline,
                    distance_label=label,
                    distance_km=None,  # multi-sport (spec §5.4)
                    event_date=race_date(base_date, race),
                    source_url=page_url or ref.url,
                    raw={"bt_event_id": bt_id, "race": race, "headers": headers,
                         "file": ref.meta["file"], "imported": "manual"},
                ),
                results=results,
            ))
        return events

    @staticmethod
    def _results(rows: list[dict]) -> tuple[list[ResultIn], int]:
        out, skipped = [], 0
        for r in rows:
            name = clean_name(r.get("athlete_name") or "")
            seconds = cell_time_seconds(r.get("time"))
            pos_text = (r.get("position") or "").strip()
            if not name or not seconds:
                skipped += 1  # no time at all (DNS, or a DNF without a time)
                continue
            position = to_int(pos_text) if pos_text.isdigit() else None
            finisher = position is not None and not _NON_FINISH.match(pos_text)
            category = (r.get("race_category") or "").strip()
            out.append(ResultIn(
                athlete_name=name,
                chip_time_seconds=seconds,
                gender=category or None,  # BT publishes "Open" / "Female" categories, stored as published
                age_group=(r.get("age_group") or "").strip() or None,
                overall_rank=position,
                finisher=finisher,
                raw={**r["_raw"], "_club": r.get("club")},
            ))
        return out, skipped
