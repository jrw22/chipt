"""Idempotent writes used by the ingestion layer."""

import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from chipt.schemas import ParsedEvent, ProviderIn


async def upsert_provider(conn: AsyncConnection, p: ProviderIn) -> int:
    row = await conn.execute(
        text(
            """
            INSERT INTO provider (slug, name, base_url, ingest_type)
            VALUES (:slug, :name, :base_url, CAST(:ingest_type AS ingest_type))
            ON CONFLICT (slug) DO UPDATE
               SET name = EXCLUDED.name, base_url = EXCLUDED.base_url,
                   ingest_type = EXCLUDED.ingest_type
            RETURNING id
            """
        ),
        {**p.model_dump(), "ingest_type": p.ingest_type.value},
    )
    return row.scalar_one()


async def upsert_parsed_event(conn: AsyncConnection, provider_id: int, pe: ParsedEvent) -> tuple[int, int]:
    """Upsert an event and its results. Returns (event_id, results_written).

    Idempotent on (provider_id, external_id) for events and
    (event_id, athlete_name, chip_time_seconds) for results.
    """
    e = pe.event
    row = await conn.execute(
        text(
            """
            INSERT INTO event (provider_id, external_id, name, discipline, distance_label,
                               distance_km, event_date, location, source_url, raw, scraped_at)
            VALUES (:provider_id, :external_id, :name, CAST(:discipline AS discipline), :distance_label,
                    :distance_km, :event_date, :location, :source_url, CAST(:raw AS jsonb), now())
            ON CONFLICT (provider_id, external_id) DO UPDATE
               SET name = EXCLUDED.name, discipline = EXCLUDED.discipline,
                   distance_label = EXCLUDED.distance_label, distance_km = EXCLUDED.distance_km,
                   event_date = EXCLUDED.event_date, location = EXCLUDED.location,
                   source_url = EXCLUDED.source_url, raw = EXCLUDED.raw, scraped_at = now()
            RETURNING id
            """
        ),
        {
            "provider_id": provider_id,
            "external_id": e.external_id,
            "name": e.name,
            "discipline": e.discipline.value,
            "distance_label": e.distance_label,
            "distance_km": e.distance_km,
            "event_date": e.event_date,
            "location": e.location,
            "source_url": e.source_url,
            "raw": json.dumps(e.raw, default=str),
        },
    )
    event_id = row.scalar_one()

    # De-duplicate within the batch on the natural key before inserting.
    seen: set[tuple[str, int]] = set()
    params = []
    for r in pe.results:
        key = (r.athlete_name, r.chip_time_seconds)
        if key in seen:
            continue
        seen.add(key)
        params.append(
            {
                "event_id": event_id,
                **r.model_dump(exclude={"raw"}),
                "raw": json.dumps(r.raw, default=str),
            }
        )
    if params:
        await conn.execute(
            text(
                """
                INSERT INTO result (event_id, athlete_name, gender, age_group, chip_time_seconds,
                                    overall_rank, gender_rank, category_rank, finisher, raw)
                VALUES (:event_id, :athlete_name, :gender, :age_group, :chip_time_seconds,
                        :overall_rank, :gender_rank, :category_rank, :finisher, CAST(:raw AS jsonb))
                ON CONFLICT (event_id, athlete_name, chip_time_seconds) DO UPDATE
                   SET gender = EXCLUDED.gender, age_group = EXCLUDED.age_group,
                       overall_rank = EXCLUDED.overall_rank, gender_rank = EXCLUDED.gender_rank,
                       category_rank = EXCLUDED.category_rank, finisher = EXCLUDED.finisher,
                       raw = EXCLUDED.raw
                """
            ),
            params,
        )
    return event_id, len(params)
