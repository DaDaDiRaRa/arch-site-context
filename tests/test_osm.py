"""OSM Overpass 보완 소스의 실패 비용 계약 (app/services/osm.py).

실측(2026-08-26): Overpass 미도달 시 호출당 40.7s × 번들 경로 9회 = **366초를 태우고 결과 0건**.
`/ask`·`/compare`·`/diagnose`·`/facilities`·`/board`·`/deck/*` 가 전부 이 경로를 지난다.
OSM 은 '카카오 누락 보완용 best-effort 소스'이지 주 데이터원이 아니므로, 못 닿으면 즉시
포기해야 한다. 여기서 그 계약(첫 실패 → 나머지 건너뜀 + 정직한 note)을 못박는다.
"""

from __future__ import annotations

import httpx

from app.services import osm


class _FakeClient:
    """호출 횟수를 세는 가짜 httpx 클라이언트."""

    def __init__(self, behavior):
        self.behavior = behavior   # callable(i) -> httpx.Response | raise
        self.calls = 0

    def post(self, url, **kwargs):
        i = self.calls
        self.calls += 1
        return self.behavior(i)


def _ok(elements):
    return httpx.Response(200, json={"elements": elements})


_KINDS = ["경로당", "도서관", "학교", "병원", "약국", "공원"]


def test_first_failure_breaks_the_circuit() -> None:
    """첫 호출이 실패하면 남은 kind 는 시도조차 하지 않는다 — 타임아웃 누적 차단."""
    def boom(_i):
        raise httpx.ConnectTimeout("timed out")

    c = _FakeClient(boom)
    results, notes = osm.search_osm(37.52, 126.92, 1000, _KINDS, client=c)

    assert c.calls == 1, f"미도달인데 {c.calls}회 호출 — 서킷 브레이커가 안 걸렸다"
    assert results == []
    assert notes and "ConnectTimeout" in notes[0] and "건너뜁니다" in notes[0]
    assert "5건" in notes[0]  # 6종 중 1건 시도·5건 스킵


def test_non_200_also_breaks() -> None:
    """5xx·429 도 같은 취급 — 한 번 못 받으면 그 요청 안에선 계속 못 받는다."""
    c = _FakeClient(lambda _i: httpx.Response(429, text="rate limited"))
    results, notes = osm.search_osm(37.52, 126.92, 1000, _KINDS, client=c)
    assert c.calls == 1 and results == []
    assert notes and "미응답" in notes[0]


def test_success_path_queries_every_kind() -> None:
    """정상일 땐 종류별로 다 돈다(도달할 때의 동작은 안 바꿨다)."""
    node = {"type": "node", "lat": 37.52, "lon": 126.92, "tags": {"name": "테스트시설"}}
    c = _FakeClient(lambda _i: _ok([node]))
    results, notes = osm.search_osm(37.52, 126.92, 1000, _KINDS, client=c)

    assert c.calls == len(_KINDS) and notes == []
    assert len(results) == len(_KINDS)
    assert {r["kind"] for r in results} == set(_KINDS)


def test_failure_midway_keeps_earlier_results() -> None:
    """중간에 끊겨도 그때까지 받은 건 살린다(부분 결과 허용 — 절대 원칙 3)."""
    node = {"type": "node", "lat": 37.52, "lon": 126.92, "tags": {"name": "테스트시설"}}

    def two_then_fail(i):
        if i < 2:
            return _ok([node])
        raise httpx.ReadTimeout("slow")

    c = _FakeClient(two_then_fail)
    results, notes = osm.search_osm(37.52, 126.92, 1000, _KINDS, client=c)

    assert c.calls == 3 and len(results) == 2
    assert notes and "3건" in notes[0]  # 6종 중 2건 성공·1건 실패·3건 스킵


def test_unmapped_kinds_cost_nothing() -> None:
    """OSM 매핑 없는 kind 는 호출 자체를 안 만든다."""
    c = _FakeClient(lambda _i: _ok([]))
    results, notes = osm.search_osm(37.52, 126.92, 1000, ["카페", "편의점"], client=c)
    assert c.calls == 0 and results == [] and notes == []


def test_connect_timeout_is_short() -> None:
    """보완 소스에 20초 연결 대기는 과하다 — 3초 이하."""
    assert osm._TIMEOUT.connect <= 3.0
