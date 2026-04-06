"""Shared FastAPI dependencies."""
from __future__ import annotations

import os

from fastapi import Header, HTTPException, status

from auto_marketer.info_broker_client import InfoBrokerClient


def get_api_key(x_api_key: str | None = Header(default=None)) -> str:
    expected = os.getenv("AUTO_MARKETER_API_KEY", "")
    if not expected:
        # Fail closed: missing config means no auth is possible.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AUTO_MARKETER_API_KEY is not configured",
        )
    if not x_api_key or x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing X-API-Key",
        )
    return x_api_key


_broker_singleton: InfoBrokerClient | None = None


def get_broker_client() -> InfoBrokerClient:
    global _broker_singleton
    if _broker_singleton is None:
        _broker_singleton = InfoBrokerClient()
    return _broker_singleton


def set_broker_client(client: InfoBrokerClient) -> None:
    """Test hook to swap the singleton."""
    global _broker_singleton
    _broker_singleton = client
