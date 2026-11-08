# Changelog

All notable changes to Chipt will be documented in this file. 

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Project scaffold: `pyproject.toml` (uv), `docker-compose.yml` (Postgres 16 on host port 5433), `README.md` with setup steps and run commands.
- Typed settings loaded from `.env` (`chipt.config`).
- Canonical Pydantic schema and API contract (`chipt.schemas`).
- PostgreSQL schema with `pg_trgm` name index, plus `chipt-initdb` to apply it and seed the single MVP athlete.
- Idempotent ingest upserts, the `BaseScraper` interface, the `PoliteClient` HTTP client (robots.txt, rate limit, honest UA, retries, raw cache), shared normalisation helpers and the `chipt-ingest` CLI.

### Changed
- `.env.example`: Postgres host port is now 5433, so it doesn't clash with a native Postgres on 5432.
