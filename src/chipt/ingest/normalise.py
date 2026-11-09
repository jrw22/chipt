"""Shared normalisation helpers so every provider maps into the canonical model the same way."""

from __future__ import annotations

import re

from chipt.schemas import SINGLE_DISCIPLINES, Discipline

_TIME_RE = re.compile(r"^\s*(?:(\d+):)?(\d{1,2}):(\d{1,2})(?:[.,]\d+)?\s*$")


def parse_time_to_seconds(value: str | None) -> int | None:
    """'1:02:03' -> 3723, '45:10' -> 2710, '00:45:10.4' -> 2710. Returns None if unparseable."""
    if not value:
        return None
    m = _TIME_RE.match(value)
    if not m:
        return None
    h, mnt, s = (int(x) if x else 0 for x in m.groups())
    if mnt >= 60 or s >= 60:
        return None
    total = h * 3600 + mnt * 60 + s
    return total or None


def format_seconds(seconds: int | float | None) -> str | None:
    if seconds is None:
        return None
    seconds = int(round(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def format_pace(seconds_per_km: float | None) -> str | None:
    if seconds_per_km is None:
        return None
    total = int(round(seconds_per_km))
    return f"{total // 60}:{total % 60:02d} /km"


# Canonical (label, km) for common single-discipline running distances.
_RUN_DISTANCES: list[tuple[re.Pattern, str, float]] = [
    (re.compile(r"\bultra\b", re.I), "Ultra", None),  # type: ignore[list-item]
    (re.compile(r"\bhalf[\s-]*marathon\b|\bhm\b|13\.1", re.I), "Half Marathon", 21.0975),
    (re.compile(r"\bmarathon\b|26\.2", re.I), "Marathon", 42.195),
    (re.compile(r"\b10\s*(?:k|km)\b|10,?000\s*m", re.I), "10K", 10.0),
    (re.compile(r"\b5\s*(?:k|km)\b|5,?000\s*m|parkrun", re.I), "5K", 5.0),
    (re.compile(r"\b10\s*mile", re.I), "10 Mile", 16.0934),
    (re.compile(r"\b5\s*mile", re.I), "5 Mile", 8.04672),
]

_MULTI_DISTANCES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"70\.3|middle\s*distance|half\s*iron", re.I), "Middle Distance (70.3)"),
    (re.compile(r"\biron\s*man\b|full\s*distance|140\.6", re.I), "Full Distance (140.6)"),
    (re.compile(r"\bolympic\b|standard", re.I), "Olympic"),
    (re.compile(r"\bsprint\b", re.I), "Sprint"),
    (re.compile(r"\bsuper\s*sprint\b", re.I), "Super Sprint"),
]

_DISCIPLINE_HINTS: list[tuple[re.Pattern, Discipline]] = [
    (re.compile(r"\btri(athlon)?\b|aquabike", re.I), Discipline.triathlon),
    (re.compile(r"\bduathlon\b", re.I), Discipline.duathlon),
    (re.compile(r"\bswim|open\s*water|aquathlon", re.I), Discipline.swimming),
    (re.compile(r"\bcycl|sportive|\bbike\b|time\s*trial|gran\s*fondo", re.I), Discipline.cycling),
]


def infer_discipline(*texts: str | None, default: Discipline = Discipline.running) -> Discipline:
    blob = " ".join(t for t in texts if t)
    for pattern, d in _DISCIPLINE_HINTS:
        if pattern.search(blob):
            return d
    return default


def normalise_distance(
    discipline: Discipline, *texts: str | None
) -> tuple[str | None, float | None]:
    """Return (distance_label, distance_km) from free text such as race/course names.

    distance_km is None for multi-sport (spec §5.4). Returns (None, None) if unknown;
    callers may then fall back to a parsed numeric km (see `km_label`).
    """
    blob = " ".join(t for t in texts if t)
    if discipline not in SINGLE_DISCIPLINES:
        # Aquabike (swim + bike, no run) is filed under triathlon but must never be compared
        # with a triathlon of the same distance, so it gets its own labels.
        prefix = "Aquabike " if re.search(r"aqua\s*bike", blob, re.I) else ""
        for pattern, label in _MULTI_DISTANCES[::-1] if "super" in blob.lower() else _MULTI_DISTANCES:
            if pattern.search(blob):
                return prefix + label, None
        return (prefix.strip() or None), None
    if discipline == Discipline.running:
        for pattern, label, km in _RUN_DISTANCES:
            if pattern.search(blob):
                return label, km
    m = re.search(r"(\d+(?:\.\d+)?)\s*(km|k|mi|mile|miles|m)\b", blob, re.I)
    if m:
        qty, unit = float(m.group(1)), m.group(2).lower()
        km = qty * 1.609344 if unit.startswith("mi") else qty / 1000 if unit == "m" else qty
        return km_label(km), round(km, 3)
    return None, None


def km_label(km: float) -> str:
    """Generic label for a numeric distance, e.g. 10.0 -> '10K', 21.1 -> '21.1K'."""
    for label, ref in (("5K", 5.0), ("10K", 10.0), ("Half Marathon", 21.0975), ("Marathon", 42.195)):
        if abs(km - ref) / ref < 0.03:
            return label
    return f"{km:g}K"


def clean_name(name: str) -> str:
    """Collapse whitespace and convert 'SURNAME, First' to 'First Surname'."""
    name = re.sub(r"\s+", " ", name).strip()
    if "," in name:
        last, _, first = name.partition(",")
        name = f"{first.strip()} {last.strip()}"
    return " ".join(p.capitalize() if p.isupper() or p.islower() else p for p in name.split(" "))


def to_int(value: str | int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    m = re.search(r"\d+", value)
    return int(m.group()) if m else None
