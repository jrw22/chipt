"""FastAPI app (spec §5.8). Run: uv run uvicorn chipt.api.main:app --reload"""

from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncConnection

from chipt.analysis.timeseries import analyse_group
from chipt.config import get_settings
from chipt.db import repository as repo
from chipt.db.session import get_conn
from chipt.schemas import (
    AnalysisOut,
    ClaimIn,
    Discipline,
    FiltersOut,
    ResultDetailOut,
    GroupSummary,
    ManualResultIn,
    ResultOut,
    SearchResultOut,
    SummaryOut,
    SummaryTotals,
)

RECENT_RESULTS = 5

settings = get_settings()

app = FastAPI(title="Chipt API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _athlete_id() -> int:
    return get_settings().default_athlete_id


def _blank_to_none(value: str | None) -> str | None:
    return value.strip() or None if value is not None else None


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/search", response_model=list[SearchResultOut])
async def search(
    name: str = Query(..., min_length=1),
    discipline: Discipline | None = None,
    provider: str | None = None,
    race: str | None = None,
    age_group: str | None = None,
    limit: int | None = Query(None, ge=1, le=500),
    conn: AsyncConnection = Depends(get_conn),
) -> list[SearchResultOut]:
    name = name.strip()
    if not name:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "name must not be blank")
    s = get_settings()
    return await repo.search_results(
        conn,
        name=name,
        athlete_id=_athlete_id(),
        threshold=s.search_similarity_threshold,
        limit=limit or s.search_max_results,
        discipline=discipline.value if discipline else None,
        provider=_blank_to_none(provider),
        race=_blank_to_none(race),
        age_group=_blank_to_none(age_group),
    )


@app.get("/results/{result_id}", response_model=ResultDetailOut)
async def result_detail(result_id: int, conn: AsyncConnection = Depends(get_conn)) -> ResultDetailOut:
    result = await repo.get_result(conn, result_id, _athlete_id())
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Result not found")
    return result


@app.get("/me/results", response_model=list[ResultOut])
async def my_results(conn: AsyncConnection = Depends(get_conn)) -> list[ResultOut]:
    return await repo.list_claimed(conn, _athlete_id())


@app.post("/me/results", response_model=ResultOut, status_code=status.HTTP_201_CREATED)
async def claim(body: ClaimIn, conn: AsyncConnection = Depends(get_conn)) -> ResultOut:
    result = await repo.claim_result(conn, _athlete_id(), body.result_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Result not found")
    return result


@app.post("/me/results/manual", response_model=ResultOut, status_code=status.HTTP_201_CREATED)
async def add_manual(body: ManualResultIn, conn: AsyncConnection = Depends(get_conn)) -> ResultOut:
    """Add a result the owner typed in (for platforms with no feed, e.g. IRONMAN) and claim it."""
    return await repo.add_manual_result(conn, _athlete_id(), body)


@app.delete("/me/results/{result_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unclaim(result_id: int, conn: AsyncConnection = Depends(get_conn)) -> Response:
    await repo.unclaim_result(conn, _athlete_id(), result_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/analysis", response_model=AnalysisOut)
async def analysis(
    discipline: Discipline | None = None,
    distance_label: str | None = None,
    conn: AsyncConnection = Depends(get_conn),
) -> AnalysisOut:
    athlete_id = _athlete_id()
    groups = await repo.comparison_groups(conn, athlete_id)
    if not groups:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No claimed results")

    distance_label = _blank_to_none(distance_label)
    if discipline is None and distance_label is None:
        chosen = groups[0]  # most claimed results, tie-break most recent
    else:
        matches = [
            g
            for g in groups
            if (discipline is None or g.discipline == discipline)
            and (distance_label is None or g.distance_label == distance_label)
        ]
        if not matches:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No claimed results in this comparison group")
        chosen = matches[0]  # if only one param given, pick the largest matching group

    rows = await repo.claimed_group_rows(conn, athlete_id, chosen.discipline.value, chosen.distance_label)
    return analyse_group(rows, chosen.discipline, chosen.distance_label, available_groups=groups)


@app.get("/me/summary", response_model=SummaryOut)
async def summary(conn: AsyncConnection = Depends(get_conn)) -> SummaryOut:
    """Dashboard data: totals, every comparison group's headline numbers, and recent results.

    Empty (zero totals, no groups) rather than 404 when nothing is claimed, so the dashboard
    can render its own empty state.
    """
    athlete_id = _athlete_id()
    claimed = await repo.list_claimed(conn, athlete_id)  # newest first
    groups = await repo.comparison_groups(conn, athlete_id)
    summaries = []
    for g in groups:
        rows = await repo.claimed_group_rows(conn, athlete_id, g.discipline.value, g.distance_label)
        a = analyse_group(rows, g.discipline, g.distance_label)
        summaries.append(GroupSummary(count=g.count, **a.model_dump(exclude={"available_groups"})))
    dates = [r.event_date for r in claimed]
    return SummaryOut(
        totals=SummaryTotals(
            results=len(claimed),
            races=len({r.event_id for r in claimed}),
            disciplines=len({r.discipline for r in claimed}),
            providers=len({r.provider_slug for r in claimed}),
            first_race=min(dates, default=None),
            latest_race=max(dates, default=None),
        ),
        groups=summaries,
        recent=claimed[:RECENT_RESULTS],
    )


@app.get("/filters", response_model=FiltersOut)
async def filters(conn: AsyncConnection = Depends(get_conn)) -> FiltersOut:
    return await repo.get_filters(conn)
