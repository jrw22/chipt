"""Create / remove the throwaway athlete the web app's Playwright smoke tests run as.

The smoke tests claim and unclaim results, so they must never run as the real athlete.
They run the API with DEFAULT_ATHLETE_ID set to a dedicated test athlete created here, and
pick their search target from **RaceBest** data only (providers that opted out of AI use
are never used as fixtures).

    uv run python -m chipt.db.e2e_fixture setup --athlete-id 900 --out web/e2e/.fixture.json
    uv run python -m chipt.db.e2e_fixture teardown --athlete-id 900
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import text

from chipt.config import get_settings
from chipt.db.session import get_engine

TEST_NAME_PREFIX = "E2E test athlete"

# A finished RaceBest single-discipline result whose athlete name appears exactly once in
# the whole database, so a name search finds exactly one candidate to claim.
_FIXTURE_SQL = """
    SELECT r.id AS result_id, r.athlete_name AS name, e.name AS event_name,
           e.discipline::text AS discipline, e.distance_label
      FROM result r
      JOIN event e ON e.id = r.event_id
      JOIN provider p ON p.id = e.provider_id
     WHERE p.slug = 'racebest' AND r.finisher AND r.overall_rank IS NOT NULL
       AND e.distance_km IS NOT NULL AND length(r.athlete_name) >= 8
       AND (SELECT count(*) FROM result x WHERE lower(x.athlete_name) = lower(r.athlete_name)) = 1
     ORDER BY e.event_date DESC, r.overall_rank
     LIMIT 1
"""


def _guard(athlete_id: int) -> None:
    if athlete_id == get_settings().default_athlete_id or athlete_id < 100:
        sys.exit(f"Refusing to use athlete {athlete_id}: the e2e athlete must be a dedicated id >= 100, "
                 "never the real one (DEFAULT_ATHLETE_ID).")


async def setup(athlete_id: int, out: Path) -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        clash = (await conn.execute(
            text("SELECT display_name FROM athlete WHERE id = :id"), {"id": athlete_id})).scalar()
        if clash is not None and not clash.startswith(TEST_NAME_PREFIX):
            sys.exit(f"Athlete {athlete_id} exists and isn't an e2e test athlete ({clash!r}); pick another id.")
        await conn.execute(
            text("INSERT INTO athlete (id, display_name) VALUES (:id, :name) "
                 "ON CONFLICT (id) DO UPDATE SET display_name = EXCLUDED.display_name"),
            {"id": athlete_id, "name": f"{TEST_NAME_PREFIX} (temporary)"},
        )
        await conn.execute(text("DELETE FROM claimed_result WHERE athlete_id = :id"), {"id": athlete_id})
        row = (await conn.execute(text(_FIXTURE_SQL))).mappings().first()
    await engine.dispose()
    if row is None:
        sys.exit("No suitable RaceBest result found. Ingest RaceBest first: uv run chipt-ingest racebest")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"athleteId": athlete_id, **{k: row[k] for k in row.keys()}}, indent=2))
    print(f"e2e athlete {athlete_id} ready; fixture written to {out}")


async def teardown(athlete_id: int) -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        # Claims cascade with the athlete. Only ever delete a test athlete.
        await conn.execute(
            text("DELETE FROM athlete WHERE id = :id AND display_name LIKE :prefix"),
            {"id": athlete_id, "prefix": f"{TEST_NAME_PREFIX}%"},
        )
    await engine.dispose()
    print(f"e2e athlete {athlete_id} removed")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("action", choices=["setup", "teardown"])
    ap.add_argument("--athlete-id", type=int, default=900)
    ap.add_argument("--out", type=Path, default=Path("web/e2e/.fixture.json"))
    args = ap.parse_args()
    _guard(args.athlete_id)
    asyncio.run(setup(args.athlete_id, args.out) if args.action == "setup" else teardown(args.athlete_id))


if __name__ == "__main__":
    main()
