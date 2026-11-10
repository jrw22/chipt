"""Canonical Pydantic schema (spec §5.4) and API response models (spec §5.8).

This module is the shared contract between ingestion, the API and the UI.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Discipline(str, Enum):
    running = "running"
    cycling = "cycling"
    swimming = "swimming"
    triathlon = "triathlon"
    duathlon = "duathlon"


SINGLE_DISCIPLINES = {Discipline.running, Discipline.cycling, Discipline.swimming}


class IngestType(str, Enum):
    scrape = "scrape"
    api = "api"
    manual = "manual"  # route 3: files the owner saved in their own browser (chipt-import)


# --------------------------------------------------------------------------- #
# Ingestion records (what a scraper's parse() produces)
# --------------------------------------------------------------------------- #


class ProviderIn(BaseModel):
    slug: str
    name: str
    base_url: str
    ingest_type: IngestType = IngestType.scrape


class EventIn(BaseModel):
    external_id: str = Field(description="Provider's own event id; idempotency key with provider")
    name: str
    discipline: Discipline
    distance_label: str = Field(description="Comparability key, e.g. 10K, Half Marathon, Olympic")
    distance_km: float | None = Field(None, description="Single-discipline only; None for multi-sport")
    event_date: date
    location: str | None = None
    source_url: str
    raw: dict[str, Any] = Field(default_factory=dict)


class ResultIn(BaseModel):
    athlete_name: str
    chip_time_seconds: int
    gender: str | None = None
    age_group: str | None = Field(None, description="As the race published it")
    overall_rank: int | None = None
    gender_rank: int | None = None
    category_rank: int | None = None
    finisher: bool = True
    raw: dict[str, Any] = Field(default_factory=dict)


class ParsedEvent(BaseModel):
    """One event plus all of its results: the unit a scraper upserts."""

    event: EventIn
    results: list[ResultIn]


# --------------------------------------------------------------------------- #
# API response models
# --------------------------------------------------------------------------- #


class ResultOut(BaseModel):
    id: int
    athlete_name: str
    gender: str | None
    age_group: str | None
    chip_time_seconds: int
    chip_time: str = Field(description="HH:MM:SS")
    overall_rank: int | None
    gender_rank: int | None
    category_rank: int | None
    finisher: bool
    time_source: Literal["chip", "gun", "unspecified"] = Field(
        "unspecified", description="What chip_time_seconds holds: chip time, gun time, or a time the race didn't label"
    )
    event_id: int
    event_name: str
    event_date: date
    discipline: Discipline
    distance_label: str
    distance_km: float | None
    location: str | None
    source_url: str
    provider_slug: str
    provider_name: str
    claimed: bool = False


class SearchResultOut(ResultOut):
    score: float = Field(description="Match confidence 0-1 (pg_trgm similarity)")


class ResultDetailOut(ResultOut):
    raw: dict[str, Any] = Field(default_factory=dict)
    # Field sizes for "N of M" positions. Finishers only (DNFs excluded).
    event_finishers: int = Field(0, description="Finishers in this event")
    gender_finishers: int | None = Field(None, description="Finishers in this event with the same gender; null if no gender")
    category_finishers: int | None = Field(
        None, description="Finishers in this event with the same age group; null if no age group"
    )


class ClaimIn(BaseModel):
    result_id: int


class ComparisonGroup(BaseModel):
    discipline: Discipline
    distance_label: str
    count: int


class AnalysisPoint(BaseModel):
    result_id: int
    event_name: str
    event_date: date
    chip_time_seconds: int
    chip_time: str
    pace_seconds_per_km: float | None = None
    pace: str | None = Field(None, description="M:SS /km")
    is_pb: bool = False


class AnalysisOut(BaseModel):
    discipline: Discipline
    distance_label: str
    points: list[AnalysisPoint] = Field(description="Sorted by event_date ascending")
    pb: AnalysisPoint | None
    most_recent: AnalysisPoint | None
    most_recent_vs_pb_seconds: int | None = Field(None, description="most_recent - pb; 0 means recent is PB")
    trend: str = Field(description="improving | declining | flat | insufficient_data")
    trend_seconds_per_year: float | None = Field(None, description="Linear-fit slope; negative = getting faster")
    available_groups: list[ComparisonGroup] = Field(default_factory=list)


class GroupSummary(BaseModel):
    """One comparison group's headline numbers, for the dashboard (AnalysisOut without the group list)."""

    discipline: Discipline
    distance_label: str
    count: int = Field(description="Claimed finishes in this group")
    points: list[AnalysisPoint] = Field(description="Sorted by event_date ascending (for sparklines)")
    pb: AnalysisPoint | None
    most_recent: AnalysisPoint | None
    most_recent_vs_pb_seconds: int | None = None
    trend: str
    trend_seconds_per_year: float | None = None


class SummaryTotals(BaseModel):
    results: int = Field(description="Claimed results, including DNFs")
    races: int = Field(description="Distinct events among claimed results")
    disciplines: int
    providers: int
    first_race: date | None = None
    latest_race: date | None = None


class SummaryOut(BaseModel):
    """Everything the dashboard needs in one call."""

    totals: SummaryTotals
    groups: list[GroupSummary] = Field(description="Largest group first (same order as available_groups)")
    recent: list[ResultOut] = Field(description="Latest claimed results, newest first")


class ProviderOut(BaseModel):
    slug: str
    name: str


class FiltersOut(BaseModel):
    """Values to populate search filter dropdowns."""

    disciplines: list[Discipline]
    providers: list[ProviderOut]
    races: list[str]
    age_groups: list[str]
