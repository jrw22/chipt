"""Pure analysis of one comparison group (spec §5.7). No DB access, so it is unit-testable.

Input rows need: result_id, event_name, event_date, chip_time_seconds, distance_km (nullable).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import numpy as np
import pandas as pd

from chipt.ingest.normalise import format_pace, format_seconds
from chipt.schemas import AnalysisOut, AnalysisPoint, ComparisonGroup, Discipline

# A slope within +/-1% of the mean time per year counts as "flat".
TREND_FLAT_FRACTION = 0.01
_DAYS_PER_YEAR = 365.25


def analyse_group(
    rows: Iterable[Mapping[str, Any]] | pd.DataFrame,
    discipline: Discipline | str,
    distance_label: str,
    available_groups: list[ComparisonGroup] | None = None,
) -> AnalysisOut:
    df = rows.copy() if isinstance(rows, pd.DataFrame) else pd.DataFrame(list(rows))
    base = dict(
        discipline=Discipline(discipline),
        distance_label=distance_label,
        available_groups=available_groups or [],
    )
    if df.empty:
        return AnalysisOut(points=[], pb=None, most_recent=None, trend="insufficient_data", **base)

    if "distance_km" not in df:
        df["distance_km"] = None
    df["event_date"] = pd.to_datetime(df["event_date"])
    df = df.sort_values(["event_date", "result_id"], kind="stable").reset_index(drop=True)

    km = pd.to_numeric(df["distance_km"], errors="coerce")
    df["pace_spk"] = np.where(km > 0, df["chip_time_seconds"] / km, np.nan)

    # PB: fastest time; on ties the earliest achievement is the PB.
    pb_idx = int(df["chip_time_seconds"].idxmin())

    points = [
        AnalysisPoint(
            result_id=int(r.result_id),
            event_name=r.event_name,
            event_date=r.event_date.date(),
            chip_time_seconds=int(r.chip_time_seconds),
            chip_time=format_seconds(r.chip_time_seconds),
            pace_seconds_per_km=None if pd.isna(r.pace_spk) else round(float(r.pace_spk), 2),
            pace=None if pd.isna(r.pace_spk) else format_pace(r.pace_spk),
            is_pb=(i == pb_idx),
        )
        for i, r in enumerate(df.itertuples(index=False))
    ]
    pb = points[pb_idx]
    most_recent = points[-1]

    trend, slope = _trend(df)
    return AnalysisOut(
        points=points,
        pb=pb,
        most_recent=most_recent,
        most_recent_vs_pb_seconds=most_recent.chip_time_seconds - pb.chip_time_seconds,
        trend=trend,
        trend_seconds_per_year=slope,
        **base,
    )


def _trend(df: pd.DataFrame) -> tuple[str, float | None]:
    """Linear fit of chip seconds vs fractional years since the first event."""
    if len(df) < 2 or df["event_date"].nunique() < 2:
        return "insufficient_data", None
    years = (df["event_date"] - df["event_date"].min()).dt.days.to_numpy(dtype=float) / _DAYS_PER_YEAR
    secs = df["chip_time_seconds"].to_numpy(dtype=float)
    slope = float(np.polyfit(years, secs, 1)[0])
    tolerance = TREND_FLAT_FRACTION * secs.mean()
    if slope < -tolerance:
        trend = "improving"
    elif slope > tolerance:
        trend = "declining"
    else:
        trend = "flat"
    return trend, round(slope, 2)
