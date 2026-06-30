"""census_multidim 실호출 테스트 — KOSIS 키 있을 때만 (다차원 census 크랙).

핵심 회귀: 동명 시군구(중구·동구 — 광역시마다 존재) 시도 disambiguation (코드리뷰 HIGH 수정).
이름만 매칭하면 전부 첫 번째(부산)로 쏠리는 버그 → sido 로 올바른 구 선택.
"""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

load_dotenv()

pytestmark = pytest.mark.skipif(
    not os.getenv("KOSIS_KEY"), reason="KOSIS_KEY 미설정 — 실호출 skip"
)


def _biz(sido: str, gu: str):
    from app.services import census_multidim as cm
    from app.services.cache import MemoryCache

    data, _ = cm.fetch_census_indicator(
        "101", "DT_1BD1032", "T01", gu, "년", sido=sido, cache=MemoryCache()
    )
    return data


def test_same_named_district_disambiguated_by_sido() -> None:
    """대전 동구 ≠ 부산 동구 — 시도로 구별 (HIGH 버그 수정)."""
    daejeon = _biz("대전", "동구")
    busan = _biz("부산", "동구")
    assert daejeon and busan
    assert daejeon["value"] > 0 and busan["value"] > 0
    # 서로 다른 구 → 사업체수 다름 (이름만 매칭 시 둘 다 같은 값 = 버그)
    assert daejeon["value"] != busan["value"]


def test_multidim_grand_total_and_breakdown() -> None:
    """다차원 표 그랜드토탈 + 분류구성 교차 (objL 순서·breakdown)."""
    data = None
    from app.services import census_multidim as cm
    from app.services.cache import MemoryCache

    data, _ = cm.fetch_census_indicator(
        "101", "DT_1BD1032", "T01", "영등포구", "년",
        sido="서울", breakdown=True, cache=MemoryCache(),
    )
    assert data and data["value"] > 0
    # 산업대분류 구성 교차 — 상위 항목 존재
    assert len(data["breakdown"]) > 0
    assert all(isinstance(row[1], int) for row in data["breakdown"])


def test_unique_district_resolves() -> None:
    """유일명 시군구(수영구) — 정상 해석."""
    d = _biz("부산", "수영구")
    assert d and d["value"] > 0
