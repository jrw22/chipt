-- Canonical schema (project_spec.md §5.4). Idempotent: safe to re-run.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

DO $$ BEGIN
    CREATE TYPE ingest_type AS ENUM ('scrape', 'api');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE discipline AS ENUM ('running', 'cycling', 'swimming', 'triathlon', 'duathlon');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS provider (
    id          SERIAL PRIMARY KEY,
    slug        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    base_url    TEXT NOT NULL,
    ingest_type ingest_type NOT NULL DEFAULT 'scrape'
);

CREATE TABLE IF NOT EXISTS event (
    id             SERIAL PRIMARY KEY,
    provider_id    INTEGER NOT NULL REFERENCES provider(id) ON DELETE CASCADE,
    external_id    TEXT NOT NULL,
    name           TEXT NOT NULL,
    discipline     discipline NOT NULL,
    distance_label TEXT NOT NULL,
    distance_km    NUMERIC(8, 3),
    event_date     DATE NOT NULL,
    location       TEXT,
    source_url     TEXT NOT NULL,
    raw            JSONB NOT NULL DEFAULT '{}'::jsonb,
    scraped_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider_id, external_id)
);

CREATE TABLE IF NOT EXISTS result (
    id                SERIAL PRIMARY KEY,
    event_id          INTEGER NOT NULL REFERENCES event(id) ON DELETE CASCADE,
    athlete_name      TEXT NOT NULL,
    gender            TEXT,
    age_group         TEXT,
    chip_time_seconds INTEGER NOT NULL,
    overall_rank      INTEGER,
    gender_rank       INTEGER,
    category_rank     INTEGER,
    finisher          BOOLEAN NOT NULL DEFAULT TRUE,
    raw               JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- Natural key for idempotent re-ingestion of the same event.
    UNIQUE (event_id, athlete_name, chip_time_seconds)
);

CREATE INDEX IF NOT EXISTS result_athlete_name_trgm
    ON result USING gin (athlete_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS result_event_id ON result (event_id);

CREATE TABLE IF NOT EXISTS athlete (
    id           SERIAL PRIMARY KEY,
    display_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claimed_result (
    athlete_id INTEGER NOT NULL REFERENCES athlete(id) ON DELETE CASCADE,
    result_id  INTEGER NOT NULL REFERENCES result(id) ON DELETE CASCADE,
    claimed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (athlete_id, result_id)
);
