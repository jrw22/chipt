"""Polite HTTP client for scrapers: robots.txt, per-host rate limit, honest UA, retries, raw cache."""

from __future__ import annotations

import hashlib
import logging
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import httpx

from chipt.config import Settings, get_settings

log = logging.getLogger(__name__)


class RobotsDisallowed(Exception):
    pass


class PoliteClient:
    def __init__(self, cache_namespace: str, settings: Settings | None = None):
        self.s = settings or get_settings()
        self.cache_dir = Path(self.s.scraper_cache_dir) / cache_namespace
        self._client = httpx.Client(
            headers={"User-Agent": self.s.scraper_user_agent},
            timeout=self.s.scraper_request_timeout_seconds,
            follow_redirects=True,
        )
        self._last_request: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}

    # -- robots ------------------------------------------------------------- #
    def _robots_for(self, url: str) -> urllib.robotparser.RobotFileParser:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                self._throttle(parts.netloc)
                resp = self._client.get(f"{origin}/robots.txt")
                rp.parse([] if resp.status_code >= 400 else resp.text.splitlines())
            except httpx.HTTPError as exc:
                log.warning("Could not fetch robots.txt for %s (%s); treating as allow-all", origin, exc)
                rp.parse([])
            self._robots[origin] = rp
        return self._robots[origin]

    def allowed(self, url: str) -> bool:
        if not self.s.scraper_respect_robots_txt:
            return True
        return self._robots_for(url).can_fetch(self.s.scraper_user_agent, url)

    # -- rate limiting ------------------------------------------------------ #
    def _throttle(self, host: str) -> None:
        wait = self.s.scraper_rate_limit_seconds - (time.monotonic() - self._last_request.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        self._last_request[host] = time.monotonic()

    MAX_REDIRECTS = 5

    def _follow_redirects(self, resp: httpx.Response) -> httpx.Response:
        """Follow redirects one hop at a time, applying robots.txt and the rate limit to EVERY host.

        Some platforms (e.g. Eventrac) redirect to an organiser's own domain. Letting httpx follow
        redirects silently would fetch pages on a host whose robots.txt was never checked.
        """
        for _ in range(self.MAX_REDIRECTS):
            nxt = resp.next_request
            if not resp.is_redirect or nxt is None:
                return resp
            target = str(nxt.url)
            if not self.allowed(target):
                raise RobotsDisallowed(f"{resp.request.url} redirects to {target}, which robots.txt disallows")
            self._throttle(nxt.url.host)
            resp = self._client.send(nxt, follow_redirects=False)
        raise httpx.TooManyRedirects("Too many redirects", request=resp.request)

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{hashlib.sha256(key.encode()).hexdigest()[:32]}.cache"

    # -- public ------------------------------------------------------------- #
    def request(
        self,
        method: str,
        url: str,
        *,
        params: dict | None = None,
        data: dict | None = None,
        json: dict | None = None,
        headers: dict | None = None,
        use_cache: bool = True,
    ) -> str:
        """Fetch a URL and return the body text. Cached on disk by (method, url, params, body)."""
        cache_key = f"{method} {url}?{urlencode(sorted((params or {}).items()))} {data} {json}"
        path = self._cache_path(cache_key)
        if use_cache and self.s.scraper_cache_enabled and path.exists():
            return path.read_text(encoding="utf-8")

        if not self.allowed(url):
            raise RobotsDisallowed(url)

        host = urlsplit(url).netloc
        last_exc: Exception | None = None
        for attempt in range(1, self.s.scraper_max_retries + 1):
            self._throttle(host)
            try:
                resp = self._client.request(method, url, params=params, data=data, json=json, headers=headers,
                                            follow_redirects=False)
                resp = self._follow_redirects(resp)
                if resp.status_code in (429, 500, 502, 503, 504):
                    raise httpx.HTTPStatusError(f"{resp.status_code}", request=resp.request, response=resp)
                resp.raise_for_status()
                body = resp.text
                if self.s.scraper_cache_enabled:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(body, encoding="utf-8")
                return body
            except httpx.HTTPError as exc:
                last_exc = exc
                log.warning("Request failed (%s/%s) %s: %s", attempt, self.s.scraper_max_retries, url, exc)
                time.sleep(self.s.scraper_rate_limit_seconds * attempt)
        raise RuntimeError(f"Giving up on {url}") from last_exc

    def get(self, url: str, **kw) -> str:
        return self.request("GET", url, **kw)

    def post(self, url: str, **kw) -> str:
        return self.request("POST", url, **kw)

    def close(self) -> None:
        self._client.close()
