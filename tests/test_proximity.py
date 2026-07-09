"""S1 — 데이터 근접도 레이어 단위테스트 (네트워크 불필요).

proximity 는 순수 메타데이터 — scope_level(자유문자열)을 하나의 정규화된 축
(대지>반경>읍면동>시군구>proxy)으로 통일한다. 새 숫자를 만들지 않는다 (절대 원칙 1·2).
Fact/DemandSignal 은 scope_level 에서 자동 유도, SupplySignal 은 개수가 항상 반경 실측이라 '반경'.
"""

from __future__ import annotations

from app.schemas.diagnose import DemandSignal, SupplySignal
from app.schemas.proximity import (
    PROXIMITY_ORDER,
    proximity_of,
    proximity_rank,
)
from app.schemas.region import Fact


# ── 매퍼: scope_level → 정규화 등급 ─────────────────────────────────────────
def test_proximity_of_known_levels() -> None:
    assert proximity_of("반경") == "반경"
    assert proximity_of("읍면동") == "읍면동"
    assert proximity_of("시군구") == "시군구"
    # 별칭도 정규화
    assert proximity_of("행정동") == "읍면동"
    assert proximity_of("필지") == "대지"


def test_proximity_of_missing_returns_none() -> None:
    # 비거나 알 수 없으면 억지로 채우지 않는다 (절대 원칙 3)
    assert proximity_of(None) is None
    assert proximity_of("") is None
    assert proximity_of("알수없는값") is None


# ── 정렬: 대지에 가까울수록 앞 ───────────────────────────────────────────────
def test_proximity_rank_orders_site_first() -> None:
    shuffled = ["시군구", "반경", "proxy", "대지", "읍면동"]
    assert sorted(shuffled, key=proximity_rank) == PROXIMITY_ORDER
    # 알 수 없는 등급은 최하위
    assert proximity_rank("대지") < proximity_rank("시군구") < proximity_rank(None)


# ── Fact 자동 유도 ──────────────────────────────────────────────────────────
def test_fact_derives_proximity_from_scope_level() -> None:
    f = Fact(item="고령인구비율", value=20.6, unit="%", source_tbl="DT_1B04005N",
             year=2025, scope="여의동", scope_level="읍면동")
    assert f.proximity == "읍면동"

    g = Fact(item="1인가구비율", value=38.2, unit="%", source_tbl="DT_1JC1511",
             year=2024, scope="영등포구", scope_level="시군구")
    assert g.proximity == "시군구"


def test_fact_without_scope_level_has_no_proximity() -> None:
    f = Fact(item="x", value=1, unit="%", source_tbl="t", year=2025)
    assert f.proximity is None


def test_fact_explicit_proximity_is_respected() -> None:
    # /site 필지 값 등은 scope_level 과 무관하게 명시 가능 (S3 통합 풀 대비)
    f = Fact(item="개별공시지가", value=29793000, unit="원/㎡", source_tbl="VWorld",
             year=2025, scope_level="시군구", proximity="대지")
    assert f.proximity == "대지"


# ── DemandSignal / SupplySignal ─────────────────────────────────────────────
def test_demand_signal_derives_proximity() -> None:
    d = DemandSignal(item="유소년인구비율", value=8.3, national_avg=10.3, unit="%",
                     level="낮음", source_tbl="DT_1B04005N", year=2025,
                     scope="반경 1000m", scope_level="반경")
    assert d.proximity == "반경"


def test_supply_signal_is_radius_by_default() -> None:
    # 공급 개수는 항상 반경 내 실측 → '반경'
    s = SupplySignal(kinds=["어린이집"], count=12, radius=1000, level="보통")
    assert s.proximity == "반경"
