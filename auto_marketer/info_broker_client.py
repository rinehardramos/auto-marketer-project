"""HTTP client for the sibling `info-broker` service.

auto-marketer no longer ingests, scrapes, or grades — all of that lives in
info-broker. This client is the ONLY way the marketing pipeline pulls
prospect data.
"""
from __future__ import annotations

import os
from typing import Any

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class InfoBrokerError(RuntimeError):
    """Raised when the info-broker API returns a non-retryable error."""


class InfoBrokerRetryable(InfoBrokerError):
    """Raised on transient failures (5xx, network) so tenacity can retry."""


_RETRYABLE = (
    requests.ConnectionError,
    requests.Timeout,
    InfoBrokerRetryable,
)


class InfoBrokerClient:
    """Thin REST wrapper around info-broker.

    Reads `INFO_BROKER_BASE_URL` (default ``http://localhost:8000``) and
    `INFO_BROKER_API_KEY` from the environment unless overridden.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: int = 30,
    ) -> None:
        self.base_url = (base_url or os.getenv("INFO_BROKER_BASE_URL", "http://localhost:8000")).rstrip("/")
        self.api_key = api_key or os.getenv("INFO_BROKER_API_KEY", "")
        self.timeout = timeout
        self._session = requests.Session()

    # ------------------------------------------------------------------ utils
    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key, "Accept": "application/json"}

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry=retry_if_exception_type(_RETRYABLE),
    )
    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self.base_url}{path}"
        try:
            resp = self._session.request(
                method,
                url,
                headers=self._headers(),
                timeout=self.timeout,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise InfoBrokerRetryable(f"Network error calling {url}: {exc}") from exc
        if resp.status_code >= 500:
            raise InfoBrokerRetryable(f"info-broker {resp.status_code} at {url}: {resp.text[:200]}")
        if resp.status_code >= 400:
            # Don't retry 4xx — bad input.
            raise InfoBrokerError(f"info-broker {resp.status_code} at {url}: {resp.text[:200]}")
        if not resp.content:
            return None
        try:
            return resp.json()
        except ValueError as exc:
            raise InfoBrokerError(f"info-broker returned non-JSON from {url}") from exc

    # ----------------------------------------------------------------- public
    def list_profiles(
        self,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status is not None:
            params["status"] = status
        result = self._request("GET", "/profiles", params=params)
        if isinstance(result, dict) and "profiles" in result:
            return list(result["profiles"])
        return list(result or [])

    def get_profile(self, profile_id: str) -> dict:
        return self._request("GET", f"/profiles/{profile_id}")

    def search(self, query: str, top_k: int = 20) -> list[dict]:
        result = self._request("POST", "/search", json={"query": query, "top_k": top_k})
        if isinstance(result, dict) and "results" in result:
            return list(result["results"])
        return list(result or [])
