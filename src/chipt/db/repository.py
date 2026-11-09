"""Read/query and claim functions used by the API (SQLAlchemy Core, raw SQL)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from chipt.ingest.normalise import format_seconds
from chipt.schemas import (
    ComparisonGroup,
    Discipline,
    FiltersOut,
    ProviderOut,
    ResultDetailOut,
    ResultOut,
    SearchResultOut,
)

# Columns shared by every result-shaped query. Expects aliases r/e/p and a
# bind param :athlete_id for the `claimed` flag.
_RESULT_COLUMNS = """
    r.id, r.athlete_name, r.gender, r.age_group, r.chip_time_seconds,
    r.overall_rank, r.gender_rank, r.category_rank, r.finisher,
    e.id AS event_id, e.name AS event_name, e.event_date,
    e.discipline::text AS discipline, e.distance_label,
    e.distance_km::float8 AS distance_km, e.location, e.source_url,
    p.slug AS provider_slug, p.name AS provider_name,
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


async def get_result(conn: AsyncConnection, result_id: int, athlete_id: int) -> ResultDetailOut | None:
    row = (
        await conn.execute(
            text(f"SELECT {_RESULT_COLUMNS}, r.raw {_FROM} WHERE r.id = :id"),
            {"id": result_id, "athlete_id": athlete_id},
        )
    ).first()
    return ResultDetailOut(**_row_to_dict(row)) if row else None


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
    return ResultOut(**detail.model_dump(exclude={"raw"})) if detail else None


async def unclaim_result(conn: AsyncConnection, athlete_id: int, result_id: int) -> None:
    """Idempotent unclaim."""
    await conn.execute(
        text("DELETE FROM claimed_result WHERE athlete_id = :a AND result_id = :r"),
        {"a": athlete_id, "r": result_id},
    )


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
