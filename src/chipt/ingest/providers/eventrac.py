"""Eventrac scraper: results hosted on eventrac.co.uk (route 1, direct scrape).

Eventrac is an entries/events platform. Some events host their results on it; others just link
out to RaceResult, Sporthive and so on, which have their own routes and are ignored here.
Organisers often run Eventrac under their own domain (e.g. www.mccpromotions.com), and Eventrac
redirects to it. PoliteClient checks robots.txt on every redirect hop.

Legal posture (checked 2026-11-09/10, see docs/providers/eventrac.md): robots.txt allows `/e/…`
results pages and opts out no AI agents. The participant terms have no scraping clause.

Per event, the results index (`/e/<slug>/results`) lists every race: date, name and results id.
Each results page (`/e/<slug>/results/<id>`) is one race with the whole field in one table:
Position, First Name, Last Name, Gender, Time (some events add columns such as Category or Chip
Time; mapping is header-driven).

    uv run chipt-ingest eventrac
    uv run python -m chipt.ingest.providers.eventrac list lancing-10k-3750   # races on an event's index
"""

from __future__ import annotations

import argparse
import logging
import re
from datetime import datetime

from bs4 import BeautifulSoup

from chipt.config import get_settings
from chipt.ingest.base import BaseScraper, EventRef
from chipt.ingest.normalise import clean_name, infer_discipline, normalise_distance, to_int
from chipt.ingest.providers.racetec import _text, cell_time_seconds, find_results_table, parse_rows
from chipt.schemas import SINGLE_DISCIPLINES, EventIn, ParsedEvent, ProviderIn, ResultIn

log = logging.getLogger(__name__)

BASE_URL = get_settings().provider_eventrac_base_url.rstrip("/")

# Hand-picked events with several years of results hosted on Eventrac (none raced by the owner;
# chosen so the time-series analysis has history). Slugs come from /e/<slug>/results.
EVENTS: list[str] = [
    "lancing-10k-3750",                            # Lancing 10K, 6 years
    "worthing-seafront-10k-3733",                  # Worthing Seafront 10K, 4 years
    "bedgebury-forest-half-marathon-and-10k-9257",  # Bedgebury Forest Half Marathon + 10K
]
# Races on an index whose name matches this are skipped (not adult comparison races).
SKIP_RACES = re.compile(r"\bjunior|\bkids?\b|fun run|\bfamily\b|canicross|\bwalk\b|1\s*mile", re.I)

_INDEX_DATE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
_RESULTS_LINK = re.compile(r"/e/([^/]+)/results/(\d+)")


def parse_index(html: str, slug: str) -> tuple[str, list[dict]]:
    """(event title, [{results_id, race, date}]) from an event's results index page."""
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    title = _text(h1) if h1 else slug
    races = []
    for tr in soup.find_all("tr"):
        link = next((a["href"] for a in tr.find_all("a", href=True) if _RESULTS_LINK.search(a["href"])), None)
        cells = [_text(td) for td in tr.find_all("td")]
        if not link or len(cells) < 2:
            continue
        m = _INDEX_DATE.search(cells[0])
        if not m:
            continue
        day, month, year = (int(x) for x in m.groups())
        races.append({
            "results_id": _RESULTS_LINK.search(link).group(2),
            "race": cells[1],
            "date": datetime(year, month, day).date(),
        })
    return title, races


class EventracScraper(BaseScraper):
    provider = ProviderIn(slug="eventrac", name="Eventrac", base_url=BASE_URL)

    def results_url(self, slug: str, results_id: str) -> str:
        return f"{BASE_URL}/e/{slug}/results/{results_id}"

    def races(self, slug: str) -> tuple[str, list[dict]]:
        return parse_index(self.http.get(f"{BASE_URL}/e/{slug}/results"), slug)

    def discover(self) -> list[EventRef]:
        refs = []
        for slug in EVENTS:
            try:
                title, races = self.races(slug)
            except Exception:
                log.exception("Eventrac index failed for %s", slug)
                continue
            for r in races:
                if SKIP_RACES.search(r["race"]):
                    log.info("skip %s: %s", slug, r["race"])
                    continue
                refs.append(EventRef(
                    url=self.results_url(slug, r["results_id"]),
                    external_id=r["results_id"],
                    meta={"slug": slug, "event_title": title, "race": r["race"], "date": r["date"].isoformat()},
                ))
        return refs

    def ref_from_url(self, url: str) -> EventRef:
        m = _RESULTS_LINK.search(url)
        if not m:
            raise ValueError(f"Not an Eventrac results URL: {url}")
        slug, rid = m.groups()
        title, races = self.races(slug)
        r = next((x for x in races if x["results_id"] == rid), None)
        if r is None:
            raise ValueError(f"Results {rid} isn't on the {slug} index")
        return EventRef(url=self.results_url(slug, rid), external_id=rid,
                        meta={"slug": slug, "event_title": title, "race": r["race"], "date": r["date"].isoformat()})

    def fetch(self, ref: EventRef) -> str:
        return self.http.get(ref.url)

    def parse(self, ref: EventRef, raw: str) -> list[ParsedEvent]:
        soup = BeautifulSoup(raw, "html.parser")
        table, headers, mapping = find_results_table(soup)
        if table is None:
            log.error("%s: no results table found", ref.url)
            return []
        rows = parse_rows(table, headers, mapping)
        race, title = ref.meta["race"], ref.meta["event_title"]
        discipline = infer_discipline(race, title)
        # The race name alone decides the distance ("Bedgebury 10K"). The event title can name
        # several distances ("… Half Marathon & 10K"), so it's only a fallback.
        label, km = normalise_distance(discipline, race)
        if label is None:
            label, km = normalise_distance(discipline, title)
        if label is None:
            log.error("%s: unknown distance for %r; skipping", ref.url, race)
            return []
        results, skipped = self._results(rows, headers, mapping)
        log.info("%s %s %s: %d results (%d DNF), %d rows skipped", ref.meta["slug"], ref.meta["date"], label,
                 len(results), sum(not r.finisher for r in results), skipped)
        if not results:
            return []
        name = race if title.lower() in race.lower() else f"{title} — {race}"
        return [ParsedEvent(
            event=EventIn(
                external_id=ref.external_id,
                name=name,
                discipline=discipline,
                distance_label=label,
                distance_km=km if discipline in SINGLE_DISCIPLINES else None,
                event_date=datetime.fromisoformat(ref.meta["date"]).date(),
                source_url=ref.url,
                raw={**ref.meta, "headers": headers},
            ),
            results=results,
        )]

    @staticmethod
    def _results(rows: list[dict], headers: list[str], mapping: dict[int, str]) -> tuple[list[ResultIn], int]:
        """Rows -> results. A bare "Time" column is stored as `unspecified` (not claimed as gun or chip)."""
        chip_header = any("chip" in headers[i].lower() or "net" in headers[i].lower()
                          for i, f in mapping.items() if f == "chip_time")
        out, skipped = [], 0
        for r in rows:
            name = clean_name(r.get("athlete_name") or f"{r.get('first_name', '')} {r.get('last_name', '')}")
            chip = cell_time_seconds(r.get("chip_time"))
            gun = cell_time_seconds(r.get("gun_time"))
            seconds = chip or gun
            if not name or not seconds:
                skipped += 1
                continue
            raw = {k: v for k, v in r["_raw"].items() if k.lower() != "action"}  # drop claim/unclaim buttons
            if chip and chip_header:
                raw["_time_source"] = "chip"
            pos_text = (r.get("overall_rank") or "").strip()
            out.append(ResultIn(
                athlete_name=name,
                chip_time_seconds=seconds,
                gender=(r.get("gender") or "").strip() or None,
                age_group=(r.get("age_group") or "").strip() or None,
                overall_rank=to_int(pos_text) if pos_text.isdigit() else None,
                gender_rank=to_int(r.get("gender_rank")) if r.get("gender_rank") else None,
                category_rank=to_int(r.get("category_rank")) if r.get("category_rank") else None,
                raw=raw,
            ))
        # When the race publishes positions, a row with a time but no position is a DNF.
        if any(x.overall_rank is not None for x in out):
            for x in out:
                if x.overall_rank is None:
                    x.finisher = False
        return out, skipped


def _cli() -> None:
    ap = argparse.ArgumentParser(description="Eventrac helpers")
    sub = ap.add_subparsers(dest="cmd", required=True)
    lp = sub.add_parser("list", help="List the races on an event's results index")
    lp.add_argument("slug", help="e.g. lancing-10k-3750")
    args = ap.parse_args()
    logging.basicConfig(level=get_settings().log_level, format="%(levelname)s %(message)s")
    s = EventracScraper()
    try:
        title, races = s.races(args.slug)
        print(title)
        for r in races:
            flag = "  (skipped)" if SKIP_RACES.search(r["race"]) else ""
            print(f"  {r['date']}  {r['results_id']:>6}  {r['race']}{flag}")
    finally:
        s.http.close()


if __name__ == "__main__":
    _cli()
