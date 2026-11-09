"""RaceBest (https://racebest.com) scraper.

RaceBest is a UK (Yorkshire-based) entry + results platform. Each results page,
``/results/{code}``, is server-rendered by Remix and embeds the full race record
and results table as JSON in ``window.__remixContext``. We read that JSON rather
than scraping the HTML table, so this is effectively a structured feed.

Legal posture and quirks: see ``docs/providers/racebest.md``.

Payload shape (``loaderData["routes/results.$url"]``)::

    race:        {url, name, date, location, distance, distanceUnits, courseType, ...}
    raceResults: {columns: [...], data: [[...], ...], published, lastUpdated}

Columns vary per race (e.g. "Net Time"/"Gun Time", "Gender Rank" "1/157 (M)",
"Age Rank" "1/16 (MV45)", "Distance" "HM"/"10K", triathlon "Position"
"1/280 [Sprint]" with "Name / AGE / CLUB"), so rows are mapped by header name.
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from datetime import date
from typing import Any
from urllib.parse import urlsplit

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

# Suggested .env var: PROVIDER_RACEBEST_BASE_URL (read if Settings grows the field).
BASE_URL = getattr(get_settings(), "provider_racebest_base_url", "https://racebest.com").rstrip("/")

# Hand-picked races: the same race across several years (time series) plus a
# multi-distance road race and a triathlon (multi-sport -> distance_km=None).
RACES: list[dict[str, str]] = [
    {"code": "htsgw", "name": "Holmfirth 10K 2023"},
    {"code": "qs29y", "name": "Holmfirth 10K 2024"},
    {"code": "f7uw2", "name": "Holmfirth 10K 2025"},
    {"code": "x336r", "name": "Holmfirth 10K 2026"},
    {"code": "qc7vz", "name": "Vale of York Half Marathon & 10K 2024"},
    {"code": "fcy5c", "name": "Vale of York Half Marathon & 10K 2025"},
    {"code": "f629w", "name": "Harrogate Triathlon 2025"},
    {"code": "wgayx", "name": "Harrogate Triathlon 2026"},
]

_REMIX_RE = re.compile(r"window\.__remixContext\s*=\s*(\{.*?\});\s*</script>", re.S)
_RANK_RE = re.compile(r"^\s*(\d+)\s*(?:/\s*\d+)?\s*(?:\(([^)]*)\))?")  # "1/157 (M)" -> 1, "M"
_CONTEST_RE = re.compile(r"\[([^\]]+)\]")  # "1/280 [Sprint]" -> "Sprint"
_UNITS = {"kilometres": "km", "kilometers": "km", "km": "km", "miles": "mile", "mile": "mile", "metres": "m"}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "main"


def _col(columns: list[str], *names: str) -> int | None:
    """Index of the first column whose header matches one of `names` (case-insensitive)."""
    lowered = [c.strip().lower() for c in columns]
    for n in names:
        if n in lowered:
            return lowered.index(n)
    return None


def _rank(value: str | None) -> tuple[int | None, str | None]:
    if not value:
        return None, None
    m = _RANK_RE.match(value)
    if not m:
        return None, None
    return int(m.group(1)), (m.group(2) or "").strip() or None


class RacebestScraper(BaseScraper):
    provider = ProviderIn(slug="racebest", name="RaceBest", base_url=BASE_URL, ingest_type=IngestType.scrape)

    # -- discover / fetch ------------------------------------------------------ #
    def discover(self) -> list[EventRef]:
        return [EventRef(url=f"{BASE_URL}/results/{r['code']}", external_id=r["code"], meta=r) for r in RACES]

    def ref_from_url(self, url: str) -> EventRef:
        m = re.search(r"/(?:results|races)/([A-Za-z0-9]+)", urlsplit(url).path)
        if not m:
            raise ValueError(f"Not a RaceBest results URL: {url}")
        code = m.group(1)
        return EventRef(url=f"{BASE_URL}/results/{code}", external_id=code, meta={"code": code})

    def fetch(self, ref: EventRef) -> dict[str, Any]:
        html = self.http.get(ref.url)
        m = _REMIX_RE.search(html)
        if not m:
            raise ValueError(f"No __remixContext payload in {ref.url}")
        loader = json.loads(m.group(1))["state"]["loaderData"]
        data = loader.get("routes/results.$url")
        if not data or not data.get("race"):
            raise ValueError(f"No race data in {ref.url}")
        return data

    # -- parse ----------------------------------------------------------------- #
    def parse(self, ref: EventRef, raw: dict[str, Any]) -> list[ParsedEvent]:
        race = raw["race"]
        table = raw.get("raceResults") or race.get("results") or {}
        columns: list[str] = table.get("columns") or []
        rows: list[list[str]] = table.get("data") or []
        if not columns or not rows:
            log.warning("[racebest] %s has no published results", ref.url)
            return []

        name = race.get("name") or ref.meta.get("name") or ref.external_id
        discipline = infer_discipline(race.get("courseType"), name)
        race_distance = self._race_distance_text(race)

        i_pos = _col(columns, "position", "pos")
        i_dist = _col(columns, "distance", "race", "event")

        # Group rows by contest (distance/wave). Single-contest pages -> one group.
        groups: dict[str, list[list[str]]] = defaultdict(list)
        for row in rows:
            contest = ""
            if i_dist is not None and i_dist < len(row):
                contest = (row[i_dist] or "").strip()
            elif i_pos is not None and i_pos < len(row):
                cm = _CONTEST_RE.search(row[i_pos] or "")
                contest = cm.group(1).strip() if cm else ""
            groups[contest].append(row)

        event_raw = {
            k: race.get(k)
            for k in ("_id", "url", "name", "date", "startTime", "location", "distance", "distanceUnits",
                      "courseType", "status", "geoLocation", "series", "organisingBody")
        }
        event_raw["columns"] = columns
        event_raw["results_last_updated"] = table.get("lastUpdated")

        parsed: list[ParsedEvent] = []
        multi = len(groups) > 1
        for contest, contest_rows in groups.items():
            if re.search(r"relay|team", contest, re.I):
                log.info("[racebest] %s: skipping non-individual contest %r (%d rows)",
                         ref.external_id, contest, len(contest_rows))
                continue
            # Prefer the contest name ("HM", "Sprint"); fall back to the race-level distance
            # only when the page has a single contest (the race-level text can list several).
            label, km = normalise_distance(discipline, contest) if contest else (None, None)
            if not label and not multi:
                label, km = normalise_distance(discipline, race_distance, name)
            if not label:
                log.warning("[racebest] %s: could not determine distance for contest %r (%s); skipping",
                            ref.external_id, contest, race_distance)
                continue
            if discipline not in SINGLE_DISCIPLINES:
                km = None

            results, skipped = self._parse_rows(ref, columns, contest_rows)
            log.info("[racebest] %s %s / %s: %d results, %d skipped (no time / unparseable)",
                     ref.external_id, name, label, len(results), skipped)
            if not results:
                continue
            parsed.append(
                ParsedEvent(
                    event=EventIn(
                        external_id=f"{race.get('url') or ref.external_id}:{_slug(contest or label)}",
                        name=f"{name} ({label})" if multi else name,
                        discipline=discipline,
                        distance_label=label,
                        distance_km=km,
                        event_date=date.fromisoformat(race["date"]),
                        location=race.get("location") or None,
                        source_url=ref.url,
                        raw={**event_raw, "contest": contest or None},
                    ),
                    results=results,
                )
            )
        return parsed

    @staticmethod
    def _race_distance_text(race: dict[str, Any]) -> str:
        dist = (race.get("distance") or "").strip()
        unit = _UNITS.get((race.get("distanceUnits") or "").strip().lower(), "")
        return f"{dist} {unit}".strip() if re.fullmatch(r"\d+(\.\d+)?", dist) else dist

    def _parse_rows(self, ref: EventRef, columns: list[str], rows: list[list[str]]) -> tuple[list[ResultIn], int]:
        i_pos = _col(columns, "position", "pos")
        i_name = _col(columns, "name")
        i_net = _col(columns, "net time", "chip time", "nettime", "chiptime")
        i_gun = _col(columns, "gun time", "guntime")
        i_time = _col(columns, "time", "total", "finish time")
        i_gender = _col(columns, "gender rank")
        i_gender_plain = _col(columns, "gender", "sex")
        i_age = _col(columns, "age rank")
        i_cat_rank = _col(columns, "category rank", "10yr cat rank", "cat rank")
        i_cat = _col(columns, "10yr cat", "category", "cat", "age group", "age cat")

        def cell(row: list[str], i: int | None) -> str | None:
            if i is None or i >= len(row):
                return None
            v = (row[i] or "").strip()
            return v or None

        out: list[ResultIn] = []
        skipped = 0
        for row in rows:
            try:
                raw_row = {c: (row[j] if j < len(row) else None) for j, c in enumerate(columns)}
                name_cell = cell(row, i_name)
                if not name_cell:
                    skipped += 1
                    continue
                # Triathlon pages publish "Name / AGEGROUP / CLUB".
                parts = [p.strip() for p in re.split(r"\s+/(?:\s+|$)", name_cell)] if " /" in name_cell else [name_cell]
                athlete = clean_name(parts[0])
                name_age = parts[1] if len(parts) > 1 and parts[1] else None

                time_source = None
                secs = None
                for src, idx in (("Net Time", i_net), ("Time", i_time), ("Gun Time", i_gun)):
                    secs = parse_time_to_seconds(cell(row, idx))
                    if secs:
                        time_source = src
                        break
                if not secs:
                    skipped += 1  # DNF / DNS / DQ or blank time
                    continue
                if time_source == "Gun Time":
                    raw_row["_chipt_note"] = "no net/chip time published; gun time used"
                raw_row["_chipt_time_source"] = time_source

                gender_rank, gender = _rank(cell(row, i_gender))
                if gender is None:
                    gender = cell(row, i_gender_plain)
                category_rank, age_group = _rank(cell(row, i_age))
                if age_group is None:
                    age_group = name_age or cell(row, i_cat)
                if category_rank is None:
                    category_rank, cat_label = _rank(cell(row, i_cat_rank))
                    if age_group is None:
                        age_group = cat_label
                overall_rank = to_int(cell(row, i_pos))

                out.append(
                    ResultIn(
                        athlete_name=athlete,
                        chip_time_seconds=secs,
                        gender=gender,
                        age_group=age_group,
                        overall_rank=overall_rank,
                        gender_rank=gender_rank,
                        category_rank=category_rank,
                        finisher=True,
                        raw=raw_row,
                    )
                )
            except Exception:  # fail soft per row
                skipped += 1
                log.warning("[racebest] %s: could not parse row %r", ref.external_id, row, exc_info=True)
        return out, skipped
