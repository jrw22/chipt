"""RunThrough scraper: results.runthrough.co.uk (RaceTec platform, ASP.NET WebForms).

WHO RUNS THIS — read first
--------------------------
results.runthrough.co.uk's robots.txt disallows AI crawlers *and* AI agents (ClaudeBot,
Claude-User, GPTBot, ...) but has no rule for generic bots. So:

* This module was written WITHOUT fetching or inspecting the site's results pages.
* It must be run by a person, as a normal deterministic script, with the honest
  `SCRAPER_USER_AGENT` from `.env` (which must not impersonate a browser or an AI agent).
  Do not have an AI agent run it or read its output pages.
* Data from this provider must NOT be sent to LLM features (the "Later" milestone) —
  the operator has opted out of AI use. See docs/providers/runthrough.md.

Because the page layout was never seen, parsing is *header-driven*: it finds the results
table by its column headers and maps columns via the synonyms in `COLUMN_SYNONYMS`. Check
what it extracts before writing to the DB:

    uv run python -m chipt.ingest.providers.runthrough list --match "half"   # find race ids (RId)
    uv run python -m chipt.ingest.providers.runthrough dump "<results url>"  # parse one race, no DB writes
    uv run chipt-ingest runthrough                                         # ingest RACES into the DB

If `dump` shows a header mapped wrongly or not at all, add the site's header text to
`COLUMN_SYNONYMS`. That should be the only tuning needed.
"""

from __future__ import annotations

import argparse
import logging
import re
from collections import defaultdict
from datetime import date, datetime
from urllib.parse import parse_qs, urljoin, urlsplit

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
from chipt.schemas import SINGLE_DISCIPLINES, EventIn, ParsedEvent, ProviderIn, ResultIn

log = logging.getLogger(__name__)

BASE_URL = get_settings().provider_runthrough_base_url.rstrip("/")
CLIENT_ID = "16487"  # RunThrough's RaceTec client id (CId)

# --------------------------------------------------------------------------- #
# Hand-picked races. Fill in RIds after running the `list` helper. Prefer the SAME
# race across several years (time-series analysis), plus one different race.
# --------------------------------------------------------------------------- #
RACES: list[str] = []

# Used only when RACES is empty: discover() scans the race listing for these names.
RACE_NAME_PATTERNS = [r"hertfordshire half", r"battersea park", r"gainsborough"]
MAX_LISTING_PAGES = 15  # listing is 20 races/page; cap request volume
MAX_DISCOVERED = 6
MAX_RESULT_PAGES = 200  # safety cap on results pagination per race

# Normalised header text -> canonical field. Exact match after normalisation.
COLUMN_SYNONYMS: dict[str, list[str]] = {
    "overall_rank": ["pos", "position", "overall", "overall pos", "overall position", "place", "rank", "no"],
    "athlete_name": ["name", "athlete", "runner", "competitor", "participant", "full name", "athlete name"],
    "first_name": ["first name", "firstname", "forename"],
    "last_name": ["last name", "lastname", "surname"],
    "chip_time": ["chip time", "chip", "net time", "nett time", "net", "nett", "chiptime"],
    "gun_time": ["gun time", "gun", "official time", "finish time", "time", "race time", "guntime"],
    "gender": ["gender", "sex", "g"],
    "age_group": ["category", "cat", "age group", "age category", "age cat", "agegroup", "age"],
    "gender_rank": ["gender pos", "gender position", "gen pos", "sex pos", "g pos", "gender rank", "gender place"],
    "category_rank": ["cat pos", "category pos", "category position", "cat position", "cat rank",
                      "age group pos", "cat place", "category place"],
    "distance": ["race", "distance", "event", "course", "race name"],
}
_HEADER_TO_FIELD = {syn: field for field, syns in COLUMN_SYNONYMS.items() for syn in syns}

_MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec"
_DATE_LONG = re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+((?:{_MONTHS})[a-z]*)\.?,?\s+(\d{{4}})\b", re.I)
_DATE_NUM = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b")
_DISTANCE_MENTION = re.compile(
    r"\bhalf[\s-]*marathon\b|\bmarathon\b|\bultra\b|\b\d+(?:\.\d+)?\s*(?:k|km|mile|miles|mi)\b", re.I
)
_POSTBACK = re.compile(r"__doPostBack\('([^']+)','Page\$(\d+)'\)")


# --------------------------------------------------------------------------- #
# Pure parsing helpers (no network)
# --------------------------------------------------------------------------- #


def _norm_header(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.lower())).strip()


def _text(el: Tag) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()


def _header_cells(table: Tag) -> list[str]:
    thead = table.find("thead")
    row = thead.find("tr") if thead else None
    if row is None:
        row = next((tr for tr in table.find_all("tr") if tr.find("th")), None) or table.find("tr")
    return [_text(c) for c in row.find_all(["th", "td"])] if row else []


def map_headers(headers: list[str]) -> dict[int, str]:
    """Column index -> canonical field (first column wins for duplicate fields)."""
    mapping: dict[int, str] = {}
    for i, h in enumerate(headers):
        field = _HEADER_TO_FIELD.get(_norm_header(h))
        if field and field not in mapping.values():
            mapping[i] = field
    return mapping


def find_results_table(soup: BeautifulSoup) -> tuple[Tag | None, list[str], dict[int, str]]:
    """Pick the table whose headers look most like a results table."""
    best: tuple[int, Tag | None, list[str], dict[int, str]] = (0, None, [], {})
    for table in soup.find_all("table"):
        headers = _header_cells(table)
        mapping = map_headers(headers)
        fields = set(mapping.values())
        has_name = "athlete_name" in fields or {"first_name", "last_name"} <= fields
        has_time = bool(fields & {"chip_time", "gun_time"})
        if not (has_name and has_time):
            continue
        score = len(fields) * 1000 + len(table.find_all("tr"))
        if score > best[0]:
            best = (score, table, headers, mapping)
    return best[1], best[2], best[3]


def parse_rows(table: Tag, headers: list[str], mapping: dict[int, str]) -> list[dict]:
    """Return one dict per data row: canonical fields plus `_raw` (header -> cell text)."""
    rows = []
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if not cells or len(cells) < len(mapping):  # header / pager / spacer rows
            continue
        texts = [_text(c) for c in cells]
        if _POSTBACK.search(str(tr)):  # GridView pager row
            continue
        row = {field: texts[i] for i, field in mapping.items() if i < len(texts)}
        row["_raw"] = {(headers[i] if i < len(headers) and headers[i] else f"col{i}"): t
                       for i, t in enumerate(texts)}
        rows.append(row)
    return rows


def extract_event_date(soup: BeautifulSoup, *fallback_texts: str | None) -> date | None:
    """Prefer dates in headings/title, then anywhere on the page, then fallbacks (race name/listing)."""
    heading_text = " ".join(_text(el) for el in soup.find_all(["title", "h1", "h2", "h3", "h4"]))
    candidates = [heading_text, *(t for t in fallback_texts if t), _text(soup)]
    for blob in candidates:
        m = _DATE_LONG.search(blob)
        if m:
            day, month, year = m.groups()
            try:
                return datetime.strptime(f"{day} {month[:3]} {year}", "%d %b %Y").date()
            except ValueError:
                pass
        m = _DATE_NUM.search(blob)
        if m:
            day, month, year = (int(x) for x in m.groups())
            try:
                return date(year, month, day)  # UK order: d/m/y
            except ValueError:
                pass
    return None


def extract_race_name(soup: BeautifulSoup, fallback: str | None) -> str:
    for tag in ("h1", "h2", "h3"):
        el = soup.find(tag)
        if el and _text(el):
            return _text(el)
    if fallback:
        return fallback
    title = soup.find("title")
    return _text(title) if title and _text(title) else "RunThrough race"


def distance_mentions(text: str) -> set[str]:
    return {re.sub(r"\s+", "", m.lower()) for m in _DISTANCE_MENTION.findall(text or "")}


# --------------------------------------------------------------------------- #
# Scraper
# --------------------------------------------------------------------------- #


class RunThroughScraper(BaseScraper):
    provider = ProviderIn(slug="runthrough", name="RunThrough", base_url=BASE_URL)

    # -- discovery ---------------------------------------------------------- #
    def results_url(self, rid: str) -> str:
        return f"{BASE_URL}/results.aspx?CId={CLIENT_ID}&RId={rid}"

    def ref_from_url(self, url: str) -> EventRef:
        rid = parse_qs(urlsplit(url).query).get("RId", [None])[0]
        if not rid:
            raise ValueError(f"No RId in {url}")
        return EventRef(url=url, external_id=rid)

    def list_races(self, pages: int = MAX_LISTING_PAGES) -> list[dict]:
        """Scan the paginated race listing. Returns [{rid, name, url, row_text}], de-duplicated."""
        races: dict[str, dict] = {}
        for p in range(pages):
            url = f"{BASE_URL}/StartPage.aspx?CId={CLIENT_ID}&From={p * 20 + 1}&To={p * 20 + 20}"
            try:
                soup = BeautifulSoup(self.http.get(url), "html.parser")
            except Exception:
                log.exception("Listing page failed: %s", url)
                continue
            found = 0
            for a in soup.find_all("a", href=True):
                if "rid=" not in a["href"].lower():
                    continue
                full = urljoin(url, a["href"])
                rid = next((v[0] for k, v in parse_qs(urlsplit(full).query).items() if k.lower() == "rid"), None)
                if not rid or rid in races:
                    continue
                row = a.find_parent("tr") or a.parent
                races[rid] = {"rid": rid, "name": _text(a), "url": full, "row_text": _text(row) if row else ""}
                found += 1
            if found == 0:
                break  # ran past the last listing page
        return list(races.values())

    def discover(self) -> list[EventRef]:
        if RACES:
            return [EventRef(url=self.results_url(r), external_id=r) for r in RACES]
        log.warning("RACES is empty: auto-discovering by name patterns %s. Pin RIds in RACES for "
                    "a stable, hand-picked set.", RACE_NAME_PATTERNS)
        pats = [re.compile(p, re.I) for p in RACE_NAME_PATTERNS]
        refs = [
            EventRef(url=r["url"], external_id=r["rid"], meta={"listing_name": r["name"], "listing_row": r["row_text"]})
            for r in self.list_races()
            if any(p.search(r["name"]) for p in pats)
        ]
        return refs[:MAX_DISCOVERED]

    # -- fetch: page 1 plus ASP.NET GridView postback pages ------------------- #
    def fetch(self, ref: EventRef) -> list[str]:
        pages = [self.http.get(ref.url)]
        current = 1
        while len(pages) < MAX_RESULT_PAGES:
            soup = BeautifulSoup(pages[-1], "html.parser")
            # Next page = smallest page number greater than the current one (handles "..." links).
            targets = sorted(
                (int(n), target) for target, n in _POSTBACK.findall(str(soup)) if int(n) > current
            )
            if not targets:
                break
            n, target = targets[0]
            form = soup.find("form")
            fields = {
                inp["name"]: inp.get("value", "")
                for inp in (form or soup).find_all("input", attrs={"type": "hidden"})
                if inp.get("name")
            }
            fields.update({"__EVENTTARGET": target, "__EVENTARGUMENT": f"Page${n}"})
            action = urljoin(ref.url, form.get("action")) if form and form.get("action") else ref.url
            pages.append(self.http.post(action, data=fields))
            current = n
        log.info("Fetched %d results page(s) for RId %s", len(pages), ref.external_id)
        return pages

    # -- parse -------------------------------------------------------------- #
    def parse(self, ref: EventRef, raw: list[str]) -> list[ParsedEvent]:
        first = BeautifulSoup(raw[0], "html.parser")
        race_name = extract_race_name(first, ref.meta.get("listing_name"))
        event_date = extract_event_date(first, race_name, ref.meta.get("listing_name"))
        if event_date is None:
            log.error("RId %s: could not find an event date on the page; skipping (see `dump`)", ref.external_id)
            return []
        discipline = infer_discipline(race_name)

        rows: list[dict] = []
        headers: list[str] = []
        mapping: dict[int, str] = {}
        for html in raw:
            table, headers, mapping = find_results_table(BeautifulSoup(html, "html.parser"))
            if table is not None:
                rows.extend(parse_rows(table, headers, mapping))
        if not rows:
            log.error("RId %s: no results table recognised; run `dump` and extend COLUMN_SYNONYMS",
                      ref.external_id)
            return []

        # Group rows by distance: a distance column if present, else the race name.
        groups: dict[str, list[dict]] = defaultdict(list)
        if "distance" in mapping.values():
            for r in rows:
                groups[r.get("distance") or race_name].append(r)
        else:
            if len(distance_mentions(race_name)) > 1:
                log.error("RId %s: '%s' names several distances but the table has no distance column, "
                          "so results can't be split; skipping (see `dump`)", ref.external_id, race_name)
                return []
            groups[race_name] = rows

        events: list[ParsedEvent] = []
        for group_text, group_rows in groups.items():
            label, km = normalise_distance(discipline, group_text, None if group_text == race_name else race_name)
            if label is None:
                log.error("RId %s: unknown distance for '%s'; skipping group", ref.external_id, group_text)
                continue
            results, skipped = self._results(group_rows)
            log.info("RId %s %s: %d results, %d rows skipped (DNF/DNS/unparseable)",
                     ref.external_id, label, len(results), skipped)
            if not results:
                continue
            name = race_name if label.lower() in race_name.lower() else f"{race_name} — {label}"
            events.append(ParsedEvent(
                event=EventIn(
                    external_id=f"{ref.external_id}:{label}",
                    name=name,
                    discipline=discipline,
                    distance_label=label,
                    distance_km=km if discipline in SINGLE_DISCIPLINES else None,
                    event_date=event_date,
                    source_url=ref.url,
                    raw={"rid": ref.external_id, "race_name": race_name, "group": group_text,
                         "headers": headers, "pages": len(raw), **ref.meta},
                ),
                results=results,
            ))
        return events

    @staticmethod
    def _results(rows: list[dict]) -> tuple[list[ResultIn], int]:
        out, skipped = [], 0
        for r in rows:
            try:
                name = r.get("athlete_name") or f"{r.get('first_name', '')} {r.get('last_name', '')}"
                name = clean_name(name)
                chip = parse_time_to_seconds(r.get("chip_time"))
                gun = parse_time_to_seconds(r.get("gun_time"))
                seconds = chip or gun
                if not name or not seconds:
                    skipped += 1
                    continue
                raw = dict(r["_raw"])
                raw["_time_source"] = "chip" if chip else "gun"
                out.append(ResultIn(
                    athlete_name=name,
                    chip_time_seconds=seconds,
                    gender=r.get("gender") or None,
                    age_group=r.get("age_group") or None,
                    overall_rank=to_int(r.get("overall_rank")),
                    gender_rank=to_int(r.get("gender_rank")),
                    category_rank=to_int(r.get("category_rank")),
                    raw=raw,
                ))
            except Exception:  # fail soft per row
                skipped += 1
                log.debug("Unparseable row: %s", r, exc_info=True)
        return out, skipped


# --------------------------------------------------------------------------- #
# Helper CLI: list races / dry-run parse (no DB writes)
# --------------------------------------------------------------------------- #


def _cli() -> None:
    ap = argparse.ArgumentParser(description="RunThrough helpers (no DB writes)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    lp = sub.add_parser("list", help="List races on the results site with their RIds")
    lp.add_argument("--pages", type=int, default=MAX_LISTING_PAGES)
    lp.add_argument("--match", help="Case-insensitive regex filter on race name")
    dp = sub.add_parser("dump", help="Fetch + parse one race and print what would be ingested")
    dp.add_argument("url")
    dp.add_argument("--rows", type=int, default=5)
    args = ap.parse_args()
    logging.basicConfig(level=get_settings().log_level, format="%(levelname)s %(message)s")

    s = RunThroughScraper()
    try:
        if args.cmd == "list":
            pat = re.compile(args.match, re.I) if args.match else None
            for r in s.list_races(args.pages):
                if not pat or pat.search(r["name"]):
                    print(f"{r['rid']:>8}  {r['name']}  |  {r['row_text'][:80]}")
        else:
            ref = s.ref_from_url(args.url)
            pages = s.fetch(ref)
            soup = BeautifulSoup(pages[0], "html.parser")
            _, headers, mapping = find_results_table(soup)
            print(f"Race name : {extract_race_name(soup, None)}")
            print(f"Event date: {extract_event_date(soup)}")
            print(f"Pages     : {len(pages)}")
            print(f"Headers   : {headers}")
            print("Mapping   : " + ", ".join(f"{headers[i]!r}->{f}" for i, f in sorted(mapping.items())))
            unmapped = [h for i, h in enumerate(headers) if i not in mapping]
            print(f"Unmapped  : {unmapped}  (kept in raw; add to COLUMN_SYNONYMS if needed)")
            for pe in s.parse(ref, pages):
                e = pe.event
                print(f"\n== {e.name} | {e.discipline.value} / {e.distance_label} ({e.distance_km} km) "
                      f"| {e.event_date} | {len(pe.results)} results | external_id={e.external_id}")
                for r in pe.results[: args.rows]:
                    print(f"   {r.overall_rank!s:>5}  {r.athlete_name:<28} {r.chip_time_seconds:>6}s "
                          f"{r.gender or '-':<6} {r.age_group or '-':<8} via {r.raw['_time_source']}")
    finally:
        s.http.close()


if __name__ == "__main__":
    _cli()
