"""Typed application settings loaded from `.env` (see `.env.example`)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_env: str = "development"
    log_level: str = "INFO"

    # Database
    database_url: str = "postgresql+asyncpg://chipt:change-me@localhost:5433/chipt"
    search_similarity_threshold: float = 0.7
    search_max_results: int = 50

    # API
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    cors_allowed_origins: str = "http://localhost:3000"


    # MVP identity
    default_athlete_id: int = 1
    default_athlete_display_name: str = "Your Name"

    # Scraping
    scraper_user_agent: str = "ChiptBot/0.1 (+https://example.com/contact)"
    scraper_rate_limit_seconds: float = 2.0
    scraper_request_timeout_seconds: float = 30
    scraper_max_retries: int = 3
    scraper_respect_robots_txt: bool = True
    scraper_cache_dir: Path = Path("./.cache/raw")
    scraper_cache_enabled: bool = True
    playwright_headless: bool = True
    playwright_browser: str = "chromium"

    # RaceTec results host (user-run only). www.resultsbase.net (Sportstiming) stays blocked.
    provider_resultsbase_results_url: str = "https://results.resultsbase.net"
    provider_runthrough_base_url: str = "https://results.runthrough.co.uk"
    provider_eventchiptiming_base_url: str = "https://results.eventchiptiming.com"
    provider_eventrac_base_url: str = "https://www.eventrac.co.uk"
    provider_racebest_base_url: str = "https://racebest.com"
    provider_ukresults_base_url: str = "https://www.ukresults.net"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
