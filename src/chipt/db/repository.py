"""Read/query and claim functions used by the API (SQLAlchemy Core, raw SQL)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from chipt.db.ingest_repo import upsert_parsed_event, upsert_provider
from chipt.ingest.normalise import format_seconds, normalise_distance, parse_time_to_seconds
from chipt.schemas import (
    SINGLE_DISCIPLINES,
    ComparisonGroup,
    Discipline,
    EventIn,
    FiltersOut,
    IngestType,
    ManualResultIn,
    ParsedEvent,
    ProviderIn,
    ResultIn,
    ProviderOut,
    ResultDetailOut,
    ResultOut,
    SearchResultOut,
)

# Which kind of time `chip_time_seconds` holds, from what each scraper recorded in `raw`:
# RaceTec scrapers write `_time_source` (chip|gun); RaceBest/UKResults write the source column
# name in `_chipt_time_source`. A bare "Time" column doesn't say which, so it's "unspecified".
_TIME_SOURCE = """
    CASE
        WHEN r.raw->>'_time_source' IN ('chip', 'gun') THEN r.raw->>'_time_source'
        WHEN r.raw->>'_chipt_time_source' IN ('Net Time', 'ChipTime', 'Chip Time') THEN 'chip'
        WHEN r.raw->>'_chipt_time_source' IN ('Gun Time', 'GunTime') THEN 'gun'
        ELSE 'unspecified'
    END
"""

# Columns shared by every result-shaped query. Expects aliases r/e/p and a
# bind param :athlete_id for the `claimed` flag.
_RESULT_COLUMNS = f"""
    r.id, r.athlete_name, r.gender, r.age_group, r.chip_time_seconds,
    r.overall_rank, r.gender_rank, r.category_rank, r.finisher,
    {_TIME_SOURCE} AS time_source,
    e.id AS event_id, e.name AS event_name, e.event_date,
    e.discipline::text AS discipline, e.distance_label,
    e.distance_km::float8 AS distance_km, e.location, e.source_url,
    p.slug AS provider_slug, p.name AS provider_name,
    (p.slug = 'manual') AS manual_entry, r.raw->>'source_platform' AS source_platform,
    EXISTS (
        SELECT 1 FROM claimed_result c
         WHERE c.result_id = r.id AND c.athlete_id = :athlete_id
    ) AS claimed
"""

_FROM = """
    FROM result r
    JOIN event e ON e.id = r.event_id
    JOIN provider p ON p.id = e.provider_id
"""


def _row_to_dict(row: Any) -> dict[str, Any]:
    d = dict(row._mapping)
    d["chip_time"] = format_seconds(d["chip_time_seconds"])
    return d


async def search_results(
    conn: AsyncConnection,
    *,
    name: str,
    athlete_id: int,
    threshold: float,
    limit: int,
    discipline: str | None = None,
    provider: str | None = None,
    race: str | None = None,
    age_group: str | None = None,
) -> list[SearchResultOut]:
    """Fuzzy name search ranked by GREATEST(similarity, word_similarity).

    `similarity` scores whole-name matches ("Jon Smith" ~ "John Smith");
    `word_similarity` lets a partial query ("Smith") match a longer name.
    The `%` / `<%` operators use the GIN trigram index; their thresholds are
    set per-transaction to the configured value.
    """
    await conn.execute(
        text(
            "SELECT set_config('pg_trgm.similarity_threshold', :t, true),"
            "       set_config('pg_trgm.word_similarity_threshold', :t, true)"
        ),
        {"t": str(threshold)},
    )
    where = ["(r.athlete_name % :name OR :name <% r.athlete_name)"]
    params: dict[str, Any] = {"name": name, "athlete_id": athlete_id, "limit": limit}
    if discipline:
        where.append("e.discipline::text = :discipline")
        params["discipline"] = discipline
    if provider:
        where.append("p.slug = :provider")
        params["provider"] = provider
    if race:
        where.append("e.name ILIKE :race")
        params["race"] = "%" + race.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    if age_group:
        where.append("lower(r.age_group) = lower(:age_group)")
        params["age_group"] = age_group

    sql = f"""
        SELECT * FROM (
            SELECT {_RESULT_COLUMNS},
                   GREATEST(similarity(r.athlete_name, :name),
                            word_similarity(:name, r.athlete_name))::numeric(5, 4)::float8 AS score
            {_FROM}
            WHERE {' AND '.join(where)}
        ) s
        ORDER BY score DESC, event_date DESC, id
        LIMIT :limit
    """
    rows = await conn.execute(text(sql), params)
    return [SearchResultOut(**_row_to_dict(r)) for r in rows]


# Field sizes for one result's event (finishers only), for "N of M" positions.
_FIELD_SIZES = """
    (SELECT count(*) FROM result x WHERE x.event_id = r.event_id AND x.finisher) AS event_finishers,
    CASE WHEN r.gender IS NULL OR r.gender = '' THEN NULL ELSE
        (SELECT count(*) FROM result x WHERE x.event_id = r.event_id AND x.finisher AND x.gender = r.gender)
    END AS gender_finishers,
    CASE WHEN r.age_group IS NULL OR r.age_group = '' THEN NULL ELSE
        (SELECT count(*) FROM result x WHERE x.event_id = r.event_id AND x.finisher AND x.age_group = r.age_group)
    END AS category_finishers
"""


async def get_result(conn: AsyncConnection, result_id: int, athlete_id: int) -> ResultDetailOut | None:
    row = (
        await conn.execute(
            text(f"SELECT {_RESULT_COLUMNS}, r.raw, {_FIELD_SIZES} {_FROM} WHERE r.id = :id"),
            {"id": result_id, "athlete_id": athlete_id},
        )
    ).first()
    if row is None:
        return None
    detail = ResultDetailOut(**_row_to_dict(row))
    if detail.manual_entry:
        # A typed-in result is the only row in its event, so counted field sizes would read "1 of 1".
        detail.event_finishers, detail.gender_finishers, detail.category_finishers = 0, None, None
    return detail


async def list_claimed(conn: AsyncConnection, athlete_id: int) -> list[ResultOut]:
    rows = await conn.execute(
        text(
            f"""
            SELECT {_RESULT_COLUMNS}
            {_FROM}
            JOIN claimed_result cr ON cr.result_id = r.id AND cr.athlete_id = :athlete_id
            ORDER BY e.event_date DESC, r.id DESC
            """
        ),
        {"athlete_id": athlete_id},
    )
    return [ResultOut(**_row_to_dict(r)) for r in rows]


async def claim_result(conn: AsyncConnection, athlete_id: int, result_id: int) -> ResultOut | None:
    """Idempotent claim. Returns None if the result does not exist."""
    exists = (await conn.execute(text("SELECT 1 FROM result WHERE id = :id"), {"id": result_id})).first()
    if not exists:
        return None
    await conn.execute(
        text(
            "INSERT INTO claimed_result (athlete_id, result_id) VALUES (:a, :r) "
            "ON CONFLICT (athlete_id, result_id) DO NOTHING"
        ),
        {"a": athlete_id, "r": result_id},
    )
    detail = await get_result(conn, result_id, athlete_id)
    return ResultOut(**detail.model_dump(include=set(ResultOut.model_fields))) if detail else None


async def unclaim_result(conn: AsyncConnection, athlete_id: int, result_id: int) -> None:
    """Idempotent unclaim."""
    await conn.execute(
        text("DELETE FROM claimed_result WHERE athlete_id = :a AND result_id = :r"),
        {"a": athlete_id, "r": result_id},
    )


# Typed-in results (no feed exists, e.g. IRONMAN) live under one provider of their own.
MANUAL_PROVIDER = ProviderIn(slug="manual", name="Manual entry", base_url="", ingest_type=IngestType.manual)

# Platforms whose robots.txt opts out of AI: results typed in from them are flagged so future LLM
# features can exclude them (CLAUDE.md). Matched case-insensitively on `source_platform`.
_AI_OPT_OUT_PLATFORMS = ("ironman", "runthrough", "event chip timing", "eventchiptiming")


async def add_manual_result(conn: AsyncConnection, athlete_id: int, body: ManualResultIn) -> ResultOut:
    """Store a result the owner typed in and claim it for them. Idempotent: entering the same
    race, date, distance, name and time again returns the existing result."""
    athlete_name = body.athlete_name or (
        await conn.execute(text("SELECT display_name FROM athlete WHERE id = :id"), {"id": athlete_id})
    ).scalar_one()
    seconds = parse_time_to_seconds(body.chip_time)
    assert seconds is not None  # checked by ManualResultIn

    if body.discipline in SINGLE_DISCIPLINES:
        km = body.distance_km or normalise_distance(body.discipline, body.distance_label)[1]
    else:
        km = None  # multi-sport events have no single distance (spec §5.4)

    key = "|".join([body.event_name.lower(), body.event_date.isoformat(), body.discipline.value,
                    body.distance_label.lower()])
    platform = body.source_platform
    raw = {
        "entered_by": "owner",
        "entered_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_platform": platform,
        "_time_source": "chip",  # the form asks for chip time
    }
    if platform and platform.lower() in _AI_OPT_OUT_PLATFORMS:
        raw["ai_opt_out"] = True

    provider_id = await upsert_provider(conn, MANUAL_PROVIDER)
    event_id, _ = await upsert_parsed_event(
        conn,
        provider_id,
        ParsedEvent(
            event=EventIn(
                external_id=f"{athlete_id}:{hashlib.sha256(key.encode()).hexdigest()[:16]}",
                name=body.event_name,
                discipline=body.discipline,
                distance_label=body.distance_label,
                distance_km=km,
                event_date=body.event_date,
                location=body.location,
                source_url=body.source_url or "",
                raw={"entered_by": "owner", "source_platform": platform},
            ),
            results=[
                ResultIn(
                    athlete_name=athlete_name,
                    chip_time_seconds=seconds,
                    gender=body.gender,
                    age_group=body.age_group,
                    overall_rank=body.overall_rank,
                    gender_rank=body.gender_rank,
                    category_rank=body.category_rank,
                    finisher=body.finisher,
                    raw=raw,
                )
            ],
        ),
    )
    result_id = (
        await conn.execute(
            text("SELECT id FROM result WHERE event_id = :e AND athlete_name = :n AND chip_time_seconds = :t"),
            {"e": event_id, "n": athlete_name, "t": seconds},
        )
    ).scalar_one()
    claimed = await claim_result(conn, athlete_id, result_id)
    assert claimed is not None
    return claimed


async def comparison_groups(conn: AsyncConnection, athlete_id: int) -> list[ComparisonGroup]:
    """The user's comparison groups, most claimed results first (tie-break: most recent)."""
    rows = await conn.execute(
        text(
            """
            SELECT e.discipline::text AS discipline, e.distance_label, count(*) AS count
              FROM claimed_result cr
              JOIN result r ON r.id = cr.result_id
              JOIN event e ON e.id = r.event_id
             WHERE cr.athlete_id = :athlete_id
               AND r.finisher  -- DNFs can be claimed but never enter the analysis
             GROUP BY e.discipline, e.distance_label
             ORDER BY count(*) DESC, max(e.event_date) DESC, e.discipline, e.distance_label
            """
        ),
        {"athlete_id": athlete_id},
    )
    return [ComparisonGroup(**dict(r._mapping)) for r in rows]


async def claimed_group_rows(
    conn: AsyncConnection, athlete_id: int, discipline: str, distance_label: str
) -> list[dict[str, Any]]:
    """Plain rows (dicts) for one comparison group, for the analysis module."""
    rows = await conn.execute(
        text(
            """
            SELECT r.id AS result_id, e.name AS event_name, e.event_date,
                   r.chip_time_seconds, e.distance_km::float8 AS distance_km
              FROM claimed_result cr
              JOIN result r ON r.id = cr.result_id
              JOIN event e ON e.id = r.event_id
             WHERE cr.athlete_id = :athlete_id
               AND e.discipline::text = :discipline
               AND e.distance_label = :distance_label
               AND r.finisher
             ORDER BY e.event_date, r.id
            """
        ),
        {"athlete_id": athlete_id, "discipline": discipline, "distance_label": distance_label},
    )
    return [dict(r._mapping) for r in rows]


async def get_filters(conn: AsyncConnection) -> FiltersOut:
    disciplines = (
        await conn.execute(text("SELECT DISTINCT discipline FROM event ORDER BY discipline"))
    ).scalars()
    providers = await conn.execute(
        text(
            "SELECT p.slug, p.name FROM provider p "
            "WHERE EXISTS (SELECT 1 FROM event e WHERE e.provider_id = p.id) ORDER BY p.name"
        )
    )
    races = (await conn.execute(text("SELECT DISTINCT name FROM event ORDER BY name"))).scalars()
    age_groups = (
        await conn.execute(
            text("SELECT DISTINCT age_group FROM result WHERE age_group IS NOT NULL AND age_group <> '' ORDER BY 1")
        )
    ).scalars()
    return FiltersOut(
        disciplines=[Discipline(d) for d in disciplines],
        providers=[ProviderOut(**dict(p._mapping)) for p in providers],
        races=list(races),
        age_groups=list(age_groups),
    )
