"""http_retry 단위 테스트 — 네트워크 불필요 (httpx.MockTransport).

검증: 5xx만 재시도, 4xx 즉시 반환, 네트워크 예외 재시도 후 전파, 2xx 즉시.
"""

from __future__ import annotations

import httpx
import pytest

from app.services.http_retry import request_with_retry


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_5xx_retried_then_success() -> None:
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] <= 2:
            return httpx.Response(503, text="busy")
        return httpx.Response(200, text="ok")

    with _client(handler) as c:
        r = request_with_retry(c, "GET", "https://x/test", retries=2, sleep=lambda s: None)
    assert r.status_code == 200
    assert calls["n"] == 3  # 503 두 번 + 성공


def test_4xx_not_retried() -> None:
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(404, text="nope")

    with _client(handler) as c:
        r = request_with_retry(c, "GET", "https://x/test", retries=2, sleep=lambda s: None)
    assert r.status_code == 404
    assert calls["n"] == 1  # 4xx 즉시 반환


def test_5xx_exhausted_returns_last() -> None:
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(500, text="down")

    with _client(handler) as c:
        r = request_with_retry(c, "GET", "https://x/test", retries=2, sleep=lambda s: None)
    assert r.status_code == 500
    assert calls["n"] == 3  # 최초 + 재시도 2회


def test_network_error_retried_then_raised() -> None:
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        raise httpx.ConnectError("boom")

    with _client(handler) as c:
        with pytest.raises(httpx.ConnectError):
            request_with_retry(c, "GET", "https://x/test", retries=2, sleep=lambda s: None)
    assert calls["n"] == 3


def test_2xx_immediate() -> None:
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(200, text="ok")

    with _client(handler) as c:
        r = request_with_retry(c, "GET", "https://x/test", sleep=lambda s: None)
    assert r.status_code == 200
    assert calls["n"] == 1
