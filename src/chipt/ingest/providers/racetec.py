"""Shared scraper for RaceTec-hosted results sites (ASP.NET WebForms).

RaceTec (https://www.racetec.net) hosts results for several UK timing companies and
organisers under their own subdomains, all with the same URL scheme:

    <base>/StartPage.aspx?CId=<client>&From=1&To=20        # paginated race listing
    <base>/results.aspx?CId=<client>&RId=<race>[&EId=<n>]  # results for one race (EId = sub-event)

Each provider is a small subclass in its own module that sets `provider`, `BASE_URL`,
`CLIENT_ID` and its hand-picked `RACES` (see runthrough.py, eventchiptiming.py, resultsbase.py).

WHO RUNS THIS — read first
--------------------------
The RaceTec results subdomains seen so far (results.runthrough.co.uk,
results.eventchiptiming.com, results.resultsbase.net) publish a robots.txt that disallows AI crawlers *and* AI
agents (ClaudeBot, Claude-User, GPTBot, ...) but has no rule for generic bots. So:

* This code was written WITHOUT fetching or inspecting any RaceTec results page.
* Subclasses must be run by a person, as a normal deterministic script, with the honest
  `SCRAPER_USER_AGENT` from `.env` (which must not impersonate a browser or an AI agent).
  Do not have an AI agent run them or read their output pages.
* Data from these providers must NOT be sent to LLM features (the "Later" milestone).

Because the page layout was never seen, parsing is *header-driven*: it finds the results
table by its column headers and maps columns via the synonyms in `COLUMN_SYNONYMS`. Use
each provider module's helper CLI to check what it extracts before writing to the DB:

    uv run python -m chipt.ingest.providers.<slug> list --match "half"   # find race ids (RId)
    uv run python -m chipt.ingest.providers.<slug> dump "<results url>"  # parse one race, no DB writes
    uv run chipt-ingest <slug>                                         # ingest RACES into the DB

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
from chipt.schemas import SINGLE_DISCIPLINES, EventIn, ParsedEvent, ResultIn

log = logging.getLogger(__name__)

MAX_LISTING_PAGES = 15  # listing is 20 races/page; cap request volume
MAX_DISCOVERED = 6
MAX_RESULT_PAGES = 200  # default safety cap on results pagination per race (subclasses may raise it)
PROGRESS_EVERY = 25  # log fetch progress every N results pages

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
    # One column holding both ranks, e.g. "3 (12)" = 3rd in category, 12th in gender.
    "category_gender_rank": ["cat pos gen pos", "category pos gender pos", "cat pos gender pos"],
}
_HEADER_TO_FIELD = {syn: field for field, syns in COLUMN_SYNONYMS.items() for syn in syns}

_MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec"
_DATE_LONG = re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+((?:{_MONTHS})[a-z]*)\.?,?\s+(\d{{4}})\b", re.I)
_DATE_NUM = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b")
_DISTANCE_MENTION = re.compile(
    r"\bhalf[\s-]*marathon\b|\bmarathon\b|\bultra\b|\b\d+(?:\.\d+)?\s*(?:k|km|mile|miles|mi)\b", re.I
)
_POSTBACK = re.compile(r"__doPostBack\('([^']+)','Page\$(\d+)'\)")
_POSTBACK_ANY = re.compile(r"__doPostBack\(\s*'([^']*)'\s*,\s*'([^']*)'\s*\)")
# A RACES entry: "RId", "RId:EId", optionally "=<distance>" (no digits-colon inside the distance,
# which is what two specs glued together by a missing comma look like).
_RACE_SPEC = re.compile(r"^\s*(\d+)\s*(?::\s*(\d+))?\s*(?:=\s*([^=]*?))?\s*$")
_PAGE_PARAM = re.compile(r"^(?:page|pageno|pagenum|pagenumber|pg|p|pn)$", re.I)
_RANK_PAIR = re.compile(r"^\s*(\d+)\s*\(\s*(\d+)\s*\)\s*$")
_TIME_SHAPE = re.compile(r"^\d{1,2}(?::\d{2}){1,2}(?:[.,]\d+)?$")
_TIME_TOKEN = re.compile(r"\b\d{1,2}(?::\d{2}){1,2}(?:[.,]\d+)?\b")
# Sub-event link labels that say nothing about the distance.
_GENERIC_SUB_EVENT = {"", "results", "result", "overall", "all", "all results"}


# --------------------------------------------------------------------------- #
# Pure parsing helpers (no network)
# --------------------------------------------------------------------------- #


def _norm_header(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.lower())).strip()


def _text(el: Tag) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()


def query_param(url: str, name: str) -> str | None:
    """Case-insensitive query-string lookup (RaceTec links mix `RId`/`rid`)."""
    return next((v[0] for k, v in parse_qs(urlsplit(url).query).items() if k.lower() == name.lower()), None)


def race_key(rid: str, eid: str | None) -> str:
    """Provider race id used in `external_id`: `RId`, or `RId.EId` when a sub-event is selected.

    Plain `RId` (no EId) keeps external ids stable for providers that don't use EId.
    """
    return f"{rid}.{eid}" if eid else rid


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


def field_columns(headers: list[str]) -> dict[str, list[int]]:
    """Canonical field -> every column index with that header (sites repeat e.g. Name / Gun Time)."""
    cols: dict[str, list[int]] = defaultdict(list)
    for i, h in enumerate(headers):
        field = _HEADER_TO_FIELD.get(_norm_header(h))
        if field:
            cols[field].append(i)
    return dict(cols)


def parse_rows(table: Tag, headers: list[str], mapping: dict[int, str]) -> list[dict]:
    """Return one dict per data row: canonical fields plus `_raw` (header -> cell text).

    When a header repeats, each field takes the first NON-EMPTY of its columns, so a
    blank duplicate (e.g. a hidden mobile-layout copy) can't wipe out the value.
    """
    cols = field_columns(headers) or {f: [i] for i, f in mapping.items()}
    rows = []
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if not cells or len(cells) < len(mapping):  # header / pager / spacer rows
            continue
        texts = [_text(c) for c in cells]
        if _POSTBACK.search(str(tr)):  # GridView pager row
            continue
        row = {field: next((texts[i] for i in idxs if i < len(texts) and texts[i]), "")
               for field, idxs in cols.items()}
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


def extract_race_name(soup: BeautifulSoup, fallback: str | None, default: str = "RaceTec race") -> str:
    for tag in ("h1", "h2", "h3"):
        el = soup.find(tag)
        if el and _text(el):
            return _text(el)
    if fallback:
        return fallback
    title = soup.find("title")
    return _text(title) if title and _text(title) else default


def split_rank_pair(value: str | None) -> tuple[int | None, int | None]:
    """'3 (12)' -> (3, 12); '3' -> (3, None); anything else -> (None, None)."""
    m = _RANK_PAIR.match(value or "")
    if m:
        return int(m.group(1)), int(m.group(2))
    return to_int(value) if value and value.strip().isdigit() else None, None


def _page_number(text: str, *candidates: str | None) -> int | None:
    """Page number from a pager link: its text if numeric, else a number in its argument/params."""
    if text.isdigit():
        return int(text)
    for c in candidates:
        m = re.search(r"(\d+)\s*$", c or "")
        if m:
            return int(m.group(1))
    return None


def pager_links(soup: BeautifulSoup, page_url: str, rid: str) -> list[dict]:
    """Every link that looks like a results-pager link for the same race.

    Handles the usual ASP.NET styles: plain GET links with a page parameter
    (`...&PageNo=2`), `__doPostBack('<target>','Page$2')` (or any argument) in href or
    onclick. Returns [{page, kind: "get"|"post", url | target+argument}], sorted by page.
    """
    path = urlsplit(page_url).path.lower()
    found: dict[int, dict] = {}
    for a in soup.find_all("a"):
        text = _text(a)
        href, onclick = a.get("href") or "", a.get("onclick") or ""
        pb = _POSTBACK_ANY.search(href) or _POSTBACK_ANY.search(onclick)
        if pb:
            target, arg = pb.groups()
            n = _page_number(text, arg)
            if n and (arg.lower().startswith("page$") or text.isdigit()):
                found.setdefault(n, {"page": n, "kind": "post", "target": target, "argument": arg})
            continue
        if not href or href.startswith(("javascript", "#", "mailto")):
            continue
        full = urljoin(page_url, href)
        if urlsplit(full).path.lower() != path or query_param(full, "RId") not in (rid, None):
            continue
        params = {k: v[0] for k, v in parse_qs(urlsplit(full).query).items()}
        page_vals = [v for k, v in params.items() if _PAGE_PARAM.match(k)]
        if not page_vals and not text.isdigit():
            continue
        n = _page_number(text, *page_vals)
        if n and (page_vals or text.isdigit()):
            found.setdefault(n, {"page": n, "kind": "get", "url": full})
    return [found[k] for k in sorted(found)]


def cell_time_seconds(value: str | None) -> int | None:
    """Seconds from a time cell, tolerating extra text around the time (e.g. '05:15:00 *')."""
    m = _TIME_TOKEN.search(value or "")
    return parse_time_to_seconds(m.group()) if m else None


def cell_shape(value: str) -> str:
    """Describe a cell without revealing it, so `dump` output can be shared safely."""
    v = value.strip()
    if not v:
        return "empty"
    if _TIME_SHAPE.match(v):
        return "time"
    if v.isdigit():
        return "int"
    if _RANK_PAIR.match(v):
        return "int (int)"
    if v.upper() in {"DNF", "DNS", "DQ", "DSQ"}:
        return v.upper()
    if len(v) <= 4 and v.isalnum():
        return f"code[{len(v)}]"  # e.g. category/gender codes
    return f"text[{len(v.split())} word(s)]"


def distance_mentions(text: str) -> set[str]:
    return {re.sub(r"\s+", "", m.lower()) for m in _DISTANCE_MENTION.findall(text or "")}


def sub_event_links(soup: BeautifulSoup, page_url: str, rid: str) -> list[tuple[str, str, str]]:
    """Links on a results page to other sub-events (EId) of the same race: [(eid, label, url)]."""
    seen: dict[str, tuple[str, str, str]] = {}
    for a in soup.find_all("a", href=True):
        full = urljoin(page_url, a["href"])
        eid = query_param(full, "EId")
        if eid and query_param(full, "RId") == rid and eid not in seen:
            seen[eid] = (eid, _text(a), full)
    return sorted(seen.values(), key=lambda t: (len(t[0]), t[0]))


def _table_fingerprint(html: str) -> int:
    """Hash of a page's results-table rows, to spot a pager that returns the same page."""
    table, _, _ = find_results_table(BeautifulSoup(html, "html.parser"))
    return hash(_text(table)) if table is not None else hash(html)


# --------------------------------------------------------------------------- #
# Scraper
# --------------------------------------------------------------------------- #


class RaceTecScraper(BaseScraper):
    """Base for one RaceTec client. Subclasses set the class attributes below."""

    BASE_URL: str
    CLIENT_ID: str
    # Hand-picked races: "RId" for the whole race, or "RId:EId" for one sub-event, optionally
    # followed by "=<distance>" when the page doesn't say it, e.g. "10316:1=Middle Distance".
    # Prefer the SAME race across several years (time-series analysis), plus one different race.
    RACES: list[str] = []
    # Used only when RACES is empty: discover() scans the race listing for these names.
    RACE_NAME_PATTERNS: list[str] = []
    # Most results pages to follow per race. Raise it for very big races (e.g. city halves).
    MAX_RESULT_PAGES: int = MAX_RESULT_PAGES

    # -- discovery ---------------------------------------------------------- #
    def results_url(self, rid: str, eid: str | None = None) -> str:
        url = f"{self.BASE_URL}/results.aspx?CId={self.CLIENT_ID}&RId={rid}"
        return f"{url}&EId={eid}" if eid else url

    def _ref(self, rid: str, eid: str | None, url: str | None = None, **meta) -> EventRef:
        return EventRef(url=url or self.results_url(rid, eid), external_id=race_key(rid, eid),
                        meta={"rid": rid, "eid": eid, **meta})

    def ref_from_url(self, url: str) -> EventRef:
        rid = query_param(url, "RId")
        if not rid:
            raise ValueError(f"No RId in {url}")
        eid = query_param(url, "EId")
        # Reuse a distance pinned for this race in RACES, so `dump`/`--url` match a normal ingest.
        pinned = next((ref for ref in self._pinned_refs() if ref.external_id == race_key(rid, eid)), None)
        return self._ref(rid, eid, url, **({"distance_hint": pinned.meta["distance_hint"]}
                                           if pinned and pinned.meta.get("distance_hint") else {}))

    def _pinned_refs(self) -> list[EventRef]:
        refs = []
        for spec in self.RACES:
            m = _RACE_SPEC.match(spec)
            if not m or (m.group(3) and re.search(r"\d+:\d+", m.group(3))):
                raise ValueError(
                    f"[{self.provider.slug}] bad RACES entry {spec!r}: expected 'RId', 'RId:EId' or "
                    "'RId:EId=<distance>'. Two entries run together usually means a missing comma.")
            rid, eid, distance = m.groups()
            meta = {"distance_hint": distance.strip()} if distance and distance.strip() else {}
            refs.append(self._ref(rid, eid, **meta))
        keys = [r.external_id for r in refs]
        dupes = sorted({k for k in keys if keys.count(k) > 1})
        if dupes:
            raise ValueError(f"[{self.provider.slug}] RACES lists the same race twice: {dupes}")
        return refs

    def list_races(self, pages: int = MAX_LISTING_PAGES) -> list[dict]:
        """Scan the paginated race listing. Returns [{rid, name, url, row_text}], de-duplicated."""
        races: dict[str, dict] = {}
        for p in range(pages):
            url = f"{self.BASE_URL}/StartPage.aspx?CId={self.CLIENT_ID}&From={p * 20 + 1}&To={p * 20 + 20}"
            try:
                soup = BeautifulSoup(self.http.get(url), "html.parser")
            except Exception:
                log.exception("Listing page failed: %s", url)
                continue
            found = 0
            for a in soup.find_all("a", href=True):
                full = urljoin(url, a["href"])
                rid = query_param(full, "RId")
                if not rid or rid in races:
                    continue
                row = a.find_parent("tr") or a.parent
                races[rid] = {"rid": rid, "name": _text(a), "url": full, "row_text": _text(row) if row else ""}
                found += 1
            if found == 0:
                break  # ran past the last listing page
        return list(races.values())

    def discover(self) -> list[EventRef]:
        if self.RACES:
            return self._pinned_refs()
        if not self.RACE_NAME_PATTERNS:
            log.warning("[%s] RACES is empty and no RACE_NAME_PATTERNS set: nothing to ingest. "
                        "Use the `list` helper to find RIds and pin them in RACES.", self.provider.slug)
            return []
        log.warning("[%s] RACES is empty: auto-discovering by name patterns %s. Pin RIds in RACES for "
                    "a stable, hand-picked set.", self.provider.slug, self.RACE_NAME_PATTERNS)
        pats = [re.compile(p, re.I) for p in self.RACE_NAME_PATTERNS]
        refs = [
            self._ref(r["rid"], query_param(r["url"], "EId"), r["url"],
                      listing_name=r["name"], listing_row=r["row_text"])
            for r in self.list_races()
            if any(p.search(r["name"]) for p in pats)
        ]
        return refs[:MAX_DISCOVERED]

    # -- fetch: page 1 plus ASP.NET GridView postback pages ------------------- #
    def fetch(self, ref: EventRef) -> list[str]:
        """Page 1, then follow the pager (GET links or ASP.NET postbacks) until it runs out."""
        pages = [self.http.get(ref.url)]
        page_url, current = ref.url, 1
        seen_bodies = {_table_fingerprint(pages[0])}
        while True:
            soup = BeautifulSoup(pages[-1], "html.parser")
            # Next page = smallest page number greater than the current one (handles "..." links).
            nxt = next((p for p in pager_links(soup, page_url, ref.meta.get("rid", "")) if p["page"] > current), None)
            if nxt is None:
                break
            if len(pages) >= self.MAX_RESULT_PAGES:
                log.warning("%s: stopped at the %d-page cap with more pages left; results are TRUNCATED. "
                            "Raise MAX_RESULT_PAGES on %s.", ref.external_id, self.MAX_RESULT_PAGES,
                            type(self).__name__)
                break
            if nxt["kind"] == "get":
                html = self.http.get(nxt["url"])
                page_url = nxt["url"]
            else:
                form = soup.find("form")
                fields = {
                    inp["name"]: inp.get("value", "")
                    for inp in (form or soup).find_all("input", attrs={"type": "hidden"})
                    if inp.get("name")
                }
                fields.update({"__EVENTTARGET": nxt["target"], "__EVENTARGUMENT": nxt["argument"]})
                action = urljoin(page_url, form.get("action")) if form and form.get("action") else page_url
                html = self.http.post(action, data=fields)
            fp = _table_fingerprint(html)
            if fp in seen_bodies:  # pager went nowhere new: stop rather than loop
                log.warning("%s: page %d repeated an earlier page; stopping", ref.external_id, nxt["page"])
                break
            seen_bodies.add(fp)
            pages.append(html)
            current = nxt["page"]
            if len(pages) % PROGRESS_EVERY == 0:
                log.info("%s: fetched %d results pages so far", ref.external_id, len(pages))
        log.info("Fetched %d results page(s) for %s", len(pages), ref.external_id)
        return pages

    # -- parse -------------------------------------------------------------- #
    def parse(self, ref: EventRef, raw: list[str]) -> list[ParsedEvent]:
        first = BeautifulSoup(raw[0], "html.parser")
        race_name = extract_race_name(first, ref.meta.get("listing_name"), f"{self.provider.name} race")
        event_date = extract_event_date(first, race_name, ref.meta.get("listing_name"))
        if event_date is None:
            log.error("%s: could not find an event date on the page; skipping (see `dump`)", ref.external_id)
            return []
        # The current sub-event's link label (e.g. "Middle Distance Aquabike") and any distance
        # pinned in RACES ("=...") are extra hints for discipline and distance.
        eid = ref.meta.get("eid")
        sub_label = next((label for e, label, _ in sub_event_links(first, ref.url, ref.meta.get("rid", ""))
                          if e == eid), "") if eid else ""
        if sub_label.strip().lower() in _GENERIC_SUB_EVENT:
            sub_label = ""
        hint = ref.meta.get("distance_hint") or ""
        discipline = infer_discipline(race_name, sub_label, hint)

        rows: list[dict] = []
        headers: list[str] = []
        mapping: dict[int, str] = {}
        for html in raw:
            table, headers, mapping = find_results_table(BeautifulSoup(html, "html.parser"))
            if table is not None:
                rows.extend(parse_rows(table, headers, mapping))
        if not rows:
            log.error("%s: no results table recognised; run `dump` and extend COLUMN_SYNONYMS",
                      ref.external_id)
            return []

        # Group rows by distance: a distance column if present, else the race name.
        groups: dict[str, list[dict]] = defaultdict(list)
        if "distance" in mapping.values():
            for r in rows:
                groups[r.get("distance") or race_name].append(r)
        else:
            if len(distance_mentions(race_name)) > 1:
                hint = (" Try one sub-event at a time with an EId (`dump` lists them)."
                        if not ref.meta.get("eid") else "")
                log.error("%s: '%s' names several distances but the table has no distance column, "
                          "so results can't be split; skipping.%s", ref.external_id, race_name, hint)
                return []
            groups[race_name] = rows

        events: list[ParsedEvent] = []
        for group_text, group_rows in groups.items():
            if hint:  # owner-pinned distance wins (but still normalised to a canonical label)
                label, km = normalise_distance(discipline, hint, sub_label, race_name)
            else:
                label, km = normalise_distance(
                    discipline, group_text, sub_label, None if group_text == race_name else race_name)
            if label is None:
                log.error("%s: unknown distance for '%s'%s; skipping group. Pin it in RACES as "
                          "'RId:EId=<distance>'", ref.external_id, group_text,
                          f" (pinned '{hint}' not recognised)" if hint else "")
                continue
            results, skipped = self._results(group_rows)
            # When the race publishes positions, a row with a time but no position is a DNF
            # (confirmed for Event Chip Timing): keep it, but as a non-finisher.
            if any(r.overall_rank is not None for r in results):
                unranked = [r for r in results if r.overall_rank is None]
                for r in unranked:
                    r.finisher = False
                if unranked:
                    log.info("   %d row(s) with a time but no position stored as non-finishers (DNF)",
                             len(unranked))
            log.info("%s %s: %d results, %d rows skipped (DNF/DNS/unparseable)",
                     ref.external_id, label, len(results), skipped)
            if not results:
                continue
            label_words = label.lower().split(" (")[0]
            name = race_name if label_words in race_name.lower() else f"{race_name} — {label}"
            events.append(ParsedEvent(
                event=EventIn(
                    external_id=f"{ref.external_id}:{label}",
                    name=name,
                    discipline=discipline,
                    distance_label=label,
                    distance_km=km if discipline in SINGLE_DISCIPLINES else None,
                    event_date=event_date,
                    source_url=ref.url,
                    raw={"race_name": race_name, "group": group_text, "sub_event": sub_label or None,
                         "headers": headers, "pages": len(raw), **ref.meta},
                ),
                results=results,
            ))
        return events

    @staticmethod
    def _results(rows: list[dict]) -> tuple[list[ResultIn], int]:
        out, skipped = [], 0
        reasons: dict[str, int] = defaultdict(int)
        example: dict[str, str] = {}
        for r in rows:
            try:
                name = r.get("athlete_name") or f"{r.get('first_name', '')} {r.get('last_name', '')}"
                name = clean_name(name)
                chip = cell_time_seconds(r.get("chip_time"))
                gun = cell_time_seconds(r.get("gun_time"))
                seconds = chip or gun
                if not name or not seconds:
                    skipped += 1
                    reason = "no name" if not name else "no time"
                    reasons[reason] += 1
                    if reason not in example:  # shapes only, never values
                        example[reason] = (f"name={cell_shape(name)}, chip={cell_shape(r.get('chip_time', ''))}, "
                                           f"gun={cell_shape(r.get('gun_time', ''))}")
                    continue
                raw = dict(r["_raw"])
                raw["_time_source"] = "chip" if chip else "gun"
                cat_rank, gen_rank = split_rank_pair(r.get("category_gender_rank"))
                out.append(ResultIn(
                    athlete_name=name,
                    chip_time_seconds=seconds,
                    gender=r.get("gender") or None,
                    age_group=r.get("age_group") or None,
                    overall_rank=to_int(r.get("overall_rank")),
                    gender_rank=to_int(r.get("gender_rank")) if r.get("gender_rank") else gen_rank,
                    category_rank=to_int(r.get("category_rank")) if r.get("category_rank") else cat_rank,
                    raw=raw,
                ))
            except Exception:  # fail soft per row
                skipped += 1
                reasons["error"] += 1
                log.debug("Unparseable row", exc_info=True)
        for reason, n in reasons.items():
            log.info("   skipped %d row(s): %s%s", n, reason,
                     f" (first one's cell shapes: {example[reason]})" if reason in example else "")
        return out, skipped


# --------------------------------------------------------------------------- #
# Helper CLI: list races / dry-run parse (no DB writes)
# --------------------------------------------------------------------------- #


def helper_cli(scraper_cls: type[RaceTecScraper]) -> None:
    """`list` / `dump` helpers for one RaceTec provider. Call from the provider's `__main__`."""
    ap = argparse.ArgumentParser(description=f"{scraper_cls.provider.name} helpers (no DB writes)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    lp = sub.add_parser("list", help="List races on the results site with their RIds")
    lp.add_argument("--pages", type=int, default=MAX_LISTING_PAGES)
    lp.add_argument("--match", help="Case-insensitive regex filter on race name")
    dp = sub.add_parser("dump", help="Fetch + parse one race and print what would be ingested")
    dp.add_argument("url")
    dp.add_argument("--rows", type=int, default=5)
    args = ap.parse_args()
    logging.basicConfig(level=get_settings().log_level, format="%(levelname)s %(message)s")

    s = scraper_cls()
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
            table, headers, mapping = find_results_table(soup)
            print(f"Race key  : {ref.external_id}  (RId={ref.meta['rid']}, EId={ref.meta['eid']})")
            print(f"Race name : {extract_race_name(soup, None)}")
            print(f"Event date: {extract_event_date(soup)}")
            print(f"Pages     : {len(pages)}")
            print(f"Headers   : {headers}")
            print("Mapping   : " + ", ".join(f"{headers[i]!r}->{f}" for i, f in sorted(mapping.items())))
            unmapped = [h for i, h in enumerate(headers) if i not in mapping]
            print(f"Unmapped  : {unmapped}  (kept in raw; add to COLUMN_SYNONYMS if needed)")
            if table is not None:
                data = [[_text(c) for c in tr.find_all("td")] for tr in table.find_all("tr")]
                data = [d for d in data if len(d) >= len(mapping) and d][:3]
                if data:
                    print(f"Columns   : (shape of the first {len(data)} rows; no values, safe to share)")
                    width = max(len(headers), *(len(d) for d in data))
                    for i in range(width):
                        h = headers[i] if i < len(headers) else "(no header)"
                        field = mapping.get(i, "-")
                        shapes = ", ".join(cell_shape(d[i]) if i < len(d) else "missing" for d in data)
                        print(f"   [{i:>2}] {h:<20} -> {field:<22} {shapes}")
            pager = pager_links(soup, ref.url, ref.meta["rid"])
            print(f"Pager     : {len(pager)} page link(s) found on page 1"
                  + ("" if pager else " (if the site shows more pages, paste this page's pager HTML)"))
            for p in pager[:5]:
                print(f"   page {p['page']}: " + (p["url"] if p["kind"] == "get"
                                                   else f"postback target={p['target']!r} arg={p['argument']!r}"))
            subs = sub_event_links(soup, ref.url, ref.meta["rid"])
            if subs:
                print("Sub-events: (pin as 'RId:EId' in RACES to ingest one at a time)")
                for eid, label, _ in subs:
                    print(f"   EId={eid:<4} {label}")
            for pe in s.parse(ref, pages):
                e = pe.event
                print(f"\n== {e.name} | {e.discipline.value} / {e.distance_label} ({e.distance_km} km) "
                      f"| {e.event_date} | {len(pe.results)} results | external_id={e.external_id}")
                for r in pe.results[: args.rows]:
                    print(f"   {r.overall_rank!s:>5}  {r.athlete_name:<28} {r.chip_time_seconds:>6}s "
                          f"{r.gender or '-':<6} {r.age_group or '-':<8} via {r.raw['_time_source']}")
    finally:
        s.http.close()
