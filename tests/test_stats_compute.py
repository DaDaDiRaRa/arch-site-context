"""모드 A 통계 계산 단위테스트 (네트워크 불필요).

ratio 계산 method 와 census 지역코드 역추출을 결정적으로 검증한다.
값은 코드/규칙이 만든다 (절대 원칙 2), census 코드는 테이블 지역목록에서 역추출 (절대 원칙 1).
"""

from __future__ import annotations

from app.services import kosis
from app.services.cache import MemoryCache, make_key
from app.services.stats import _compute


# ── ratio 계산 (1인가구비율 = T210/T100 ×100) ────────────────────────────
def _rows():
    return [
        {"itm_id": "T100", "c2": "000", "value": 176587.0},  # 일반가구
        {"itm_id": "T210", "c2": "000", "value": 79698.0},   # 1인가구
        {"itm_id": "T300", "c2": "000", "value": 2.0},       # 평균가구원수
    ]


def test_ratio_one_person_household() -> None:
    item = {
        "method": "ratio",
        "kosis": {"num_itm": "T210", "den_itm": "T100", "objL2_pick": "000"},
    }
    assert _compute(item, _rows()) == 45.1  # 79698/176587×100


def test_ratio_missing_denominator_returns_none() -> None:
    item = {"method": "ratio", "kosis": {"num_itm": "T210", "den_itm": "T999", "objL2_pick": "000"}}
    assert _compute(item, _rows()) is None  # 분모 없음 → 추정 않고 None


def test_direct_picks_exact_c2() -> None:
    # 평균가구원수: direct T300, objL2_pick=000 → 정확히 그 분류값
    item = {"method": "direct", "kosis": {"itmId": "T300", "objL2_pick": "000"}}
    assert _compute(item, _rows()) == 2.0


# ── census 지역코드 역추출 ──────────────────────────────────────────────
def test_resolve_census_region_from_cached_map() -> None:
    # 테이블 지역목록을 캐시에 미리 심어 네트워크 없이 검증.
    cache = MemoryCache()
    ckey = make_key("kosis_regmap", "101", "DT_1JC1511", "000")
    cache.set(ckey, {"11|영등포구": "11190", "11|서울특별시": "11", "26|해운대구": "26350"})

    # 행안부 영등포구(11560) → census 11190 (시도접두 11 + 시군구명 매칭)
    code = kosis.resolve_census_region(
        "101", "DT_1JC1511", "11", "영등포구", obj_l2="000", cache=cache
    )
    assert code == "11190"


def test_resolve_census_region_unknown_returns_none() -> None:
    cache = MemoryCache()
    cache.set(make_key("kosis_regmap", "101", "DT_1JC1511", "000"), {"11|영등포구": "11190"})
    # 다른 시도 접두(없는 조합) → None (추정 금지)
    assert (
        kosis.resolve_census_region(
            "101", "DT_1JC1511", "26", "영등포구", obj_l2="000", cache=cache
        )
        is None
    )
