"""행안부 rdoa 행정동별 인구+세대 실호출 테스트 — 네트워크 있을 때만.

무키(rdoa.jumin.go.kr) · 시군구코드 5자리 · 지난달 자동탐지. 사이트 장애/구조변경은
graceful skip. 읍면동 주민등록 세대(KOSIS 미제공)를 전국·무키로 얻는지 검증.
[[jumin-rdoa-population-household-api]]
"""

from __future__ import annotations

import pytest

from app.services import jumin
from app.services.cache import MemoryCache


def test_jumin_dongjak() -> None:
    """동작구 행정동별 인구+세대 — 노량진1동 세대 검증 (슬라이드 18,457 급)."""
    data, notes = jumin.fetch_dong_stats("11590", cache=MemoryCache())
    if data is None:
        pytest.skip(f"행안부 rdoa 응답 없음(사이트 장애 가능): {notes}")
    dongs = data["dongs"]
    assert len(dongs) >= 10  # 동작구 15개 행정동
    # 노량진1동 H코드 = 카카오 coord_to_hdong 과 동일한 10자리
    nlj = dongs.get("1159051000")
    assert nlj is not None, "노량진1동(1159051000) 없음"
    assert 14000 < nlj["households"] < 22000, nlj  # 주민등록 세대 (월별 변동 여유)
    assert nlj["population"] > nlj["households"]  # 인구 > 세대 (당연)
    assert nlj["per_household"] and nlj["per_household"] > 1.0


def test_jumin_nationwide_daejeon() -> None:
    """전국 작동 실증 — 비서울(대전 서구 30170)도 무수정으로 나온다."""
    data, notes = jumin.fetch_dong_stats("30170", cache=MemoryCache())
    if data is None:
        pytest.skip(f"행안부 rdoa 응답 없음: {notes}")
    dongs = data["dongs"]
    assert len(dongs) >= 5
    # 모든 행정동에 인구·세대가 채워졌는지
    assert all(v["households"] and v["population"] for v in dongs.values())


def test_jumin_bad_code() -> None:
    """시군구코드 5자리 아니면 추정 없이 건너뜀 (절대 원칙 3) — 비네트워크."""
    data, notes = jumin.fetch_dong_stats("11", cache=MemoryCache())
    assert data is None
    assert notes and "형식 오류" in notes[0]


def test_jumin_cache_hit() -> None:
    """같은 (시군구,년월) 재호출은 캐시로 네트워크 0 — 결과 동일."""
    cache = MemoryCache()
    d1, _ = jumin.fetch_dong_stats("11590", ym="202606", cache=cache)
    if d1 is None:
        pytest.skip("행안부 rdoa 응답 없음")
    d2, _ = jumin.fetch_dong_stats("11590", ym="202606", cache=cache)
    assert d2 == d1
