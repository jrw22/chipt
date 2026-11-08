"""Thin HTTP client for the Chipt FastAPI backend (the UI never touches the DB)."""

from __future__ import annotations

from typing import Any

import httpx

from chipt.config import get_settings
from chipt.schemas import (
    AnalysisOut,
    FiltersOut,
    ResultDetailOut,
    ResultOut,
    SearchResultOut,
)

TIMEOUT_SECONDS = 15.0


class ApiError(Exception):
    """A user-presentable API failure (backend down, bad response, etc.)."""


class NotFound(ApiError):
    pass


def _base_url() -> str:
    return get_settings().api_base_url.rstrip("/")


def _request(method: str, path: str, **kwargs: Any) -> httpx.Response:
    url = f"{_base_url()}{path}"
    try:
        resp = httpx.request(method, url, timeout=TIMEOUT_SECONDS, **kwargs)
    except httpx.ConnectError as exc:
        raise ApiError(
            f"Can't reach the Chipt API at {_base_url()}. Is the backend running?"
        ) from exc
    except httpx.TimeoutException as exc:
        raise ApiError(f"The Chipt API at {_base_url()} timed out.") from exc
    except httpx.HTTPError as exc:
        raise ApiError(f"Error talking to the Chipt API: {exc}") from exc

    if resp.status_code == 404:
        raise NotFound(_detail(resp))
    if resp.status_code >= 400:
        raise ApiError(f"API error {resp.status_code} on {method} {path}: {_detail(resp)}")
    return resp


def _detail(resp: httpx.Response) -> str:
    try:
        body = resp.json()
        if isinstance(body, dict) and "detail" in body:
            return str(body["detail"])
        return str(body)
    except ValueError:
        return resp.text or resp.reason_phrase


def health() -> bool:
    try:
        return _request("GET", "/health").json().get("status") == "ok"
    except ApiError:
        return False


def get_filters() -> FiltersOut:
    return FiltersOut.model_validate(_request("GET", "/filters").json())


def search(
    name: str,
    discipline: str | None = None,
    provider: str | None = None,
    race: str | None = None,
    age_group: str | None = None,
    limit: int | None = None,
) -> list[SearchResultOut]:
    params = {
        k: v
        for k, v in {
            "name": name,
            "discipline": discipline,
            "provider": provider,
            "race": race,
            "age_group": age_group,
            "limit": limit,
        }.items()
        if v not in (None, "")
    }
    data = _request("GET", "/search", params=params).json()
    return [SearchResultOut.model_validate(r) for r in data]


def get_result(result_id: int) -> ResultDetailOut:
    return ResultDetailOut.model_validate(_request("GET", f"/results/{result_id}").json())


def my_results() -> list[ResultOut]:
    return [ResultOut.model_validate(r) for r in _request("GET", "/me/results").json()]


def claim(result_id: int) -> ResultOut:
    resp = _request("POST", "/me/results", json={"result_id": result_id})
    return ResultOut.model_validate(resp.json())


def unclaim(result_id: int) -> None:
    _request("DELETE", f"/me/results/{result_id}")


def analysis(discipline: str | None = None, distance_label: str | None = None) -> AnalysisOut | None:
    """Return the analysis for a comparison group, or None when nothing is claimed."""
    params = {}
    if discipline and distance_label:
        params = {"discipline": discipline, "distance_label": distance_label}
    try:
        return AnalysisOut.model_validate(_request("GET", "/analysis", params=params).json())
    except NotFound:
        return None
