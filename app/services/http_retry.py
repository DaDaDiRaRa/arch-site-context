"""HTTP 재시도/백오프 유틸 — arch-law-diagnose `http_retry` 이식 (INTEGRATION.md §3·§6).

원칙: **5xx·네트워크 오류만 재시도**(지수 백오프), **4xx는 즉시 반환**(재시도 무의미).
외부 API(KOSIS·카카오·VWorld·data.go.kr) 일시 장애에 견고화. 추정 없음 — 실패는 그대로 전파.

사용:
    from app.services.http_retry import request_with_retry
    r = request_with_retry(client, "GET", url, params=..., timeout=10)
"""

from __future__ import annotations

import time
from typing import Callable, Iterable

import httpx

_RETRY_STATUSES = (500, 502, 503, 504)


def request_with_retry(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    retries: int = 2,
    backoff_base: float = 0.5,
    retry_statuses: Iterable[int] = _RETRY_STATUSES,
    sleep: Callable[[float], None] = time.sleep,
    **kwargs,
) -> httpx.Response:
    """5xx·네트워크 오류 시 최대 `retries`회 재시도(백오프), 4xx·2xx는 즉시 반환.

    - 5xx 응답: 백오프 후 재시도, 소진 시 마지막 응답 반환(호출자가 상태 판단).
    - 네트워크/타임아웃 예외: 백오프 후 재시도, 소진 시 예외 전파.
    - 4xx 응답: 재시도 없이 즉시 반환 (재시도해도 동일).
    백오프 = backoff_base * 2**attempt (0.5, 1.0, …).
    """
    retry_set = set(retry_statuses)
    attempt = 0
    while True:
        try:
            resp = client.request(method, url, **kwargs)
        except (httpx.TimeoutException, httpx.TransportError):
            if attempt >= retries:
                raise
            sleep(backoff_base * (2 ** attempt))
            attempt += 1
            continue
        if resp.status_code in retry_set and attempt < retries:
            sleep(backoff_base * (2 ** attempt))
            attempt += 1
            continue
        return resp
