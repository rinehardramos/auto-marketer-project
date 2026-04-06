from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from auto_marketer.info_broker_client import InfoBrokerClient, InfoBrokerError


def _mock_response(status: int = 200, json_body=None, text: str = ""):
    r = MagicMock()
    r.status_code = status
    r.content = b"x" if json_body is not None or text else b""
    r.text = text
    r.json.return_value = json_body if json_body is not None else {}
    return r


def test_list_profiles_sends_api_key_and_params():
    client = InfoBrokerClient(base_url="http://broker.test", api_key="k1")
    with patch.object(client._session, "request") as req:
        req.return_value = _mock_response(json_body=[{"id": "1"}])
        out = client.list_profiles(status="completed", limit=10)
    assert out == [{"id": "1"}]
    args, kwargs = req.call_args
    assert args[0] == "GET"
    assert args[1] == "http://broker.test/profiles"
    assert kwargs["headers"]["X-API-Key"] == "k1"
    assert kwargs["params"]["status"] == "completed"
    assert kwargs["params"]["limit"] == 10


def test_get_profile_url():
    client = InfoBrokerClient(base_url="http://broker.test", api_key="k")
    with patch.object(client._session, "request") as req:
        req.return_value = _mock_response(json_body={"id": "abc"})
        out = client.get_profile("abc")
    assert out["id"] == "abc"
    assert req.call_args.args[1] == "http://broker.test/profiles/abc"


def test_search_posts_payload():
    client = InfoBrokerClient(base_url="http://broker.test", api_key="k")
    with patch.object(client._session, "request") as req:
        req.return_value = _mock_response(json_body={"results": [{"id": "x"}]})
        out = client.search("acme", top_k=5)
    assert out == [{"id": "x"}]
    assert req.call_args.kwargs["json"] == {"query": "acme", "top_k": 5}


def test_5xx_retries_then_raises():
    client = InfoBrokerClient(base_url="http://broker.test", api_key="k")
    with patch.object(client._session, "request") as req:
        req.return_value = _mock_response(status=500, text="boom")
        with pytest.raises(InfoBrokerError):
            client.list_profiles()
        # tenacity stop_after_attempt(3) → 3 attempts
        assert req.call_count == 3


def test_4xx_does_not_retry():
    client = InfoBrokerClient(base_url="http://broker.test", api_key="k")
    with patch.object(client._session, "request") as req:
        req.return_value = _mock_response(status=404, text="nope")
        with pytest.raises(InfoBrokerError):
            client.get_profile("missing")
        assert req.call_count == 1
