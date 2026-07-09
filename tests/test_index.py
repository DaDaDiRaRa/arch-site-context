"""T1 — 전국=100 정규화 지수 단위테스트 (네트워크 불필요).

index = value/national×100 는 기존 두 수치의 비율일 뿐 — 새 숫자 아님 (절대 원칙 2).
비율(%) 지표에만 의미 → 절대수(명·가구)·national 없음이면 None (오지수 방지). 밴드는 ±10%.
Fact·DemandSignal 이 생성 시 자동 유도되는지 확인.
"""

from __future__ import annotations

from app.schemas.diagnose import DemandSignal
from app.schemas.region import Fact, compute_index, index_band


# ── compute_index: 비율만, 절대수·무근거는 None ──────────────────────────────
def test_index_on_percentage() -> None:
    assert compute_index(22.1, 19.5, "%") == 113
    assert compute_index(8.3, 10.3, "%") == 81


def test_index_none_for_counts_and_missing_national() -> None:
    # 절대수(단위 %아님)는 national=전국총량이라 지수 무의미 → None
    assert compute_index(34066, 51000000, "명") is None
    # national 없음 → None (추정 안 함)
    assert compute_index(9320, None, "명/㎢") is None
    assert compute_index(50.0, 0, "%") is None  # 0 나눗셈 방지


def test_index_band_edges() -> None:
    assert index_band(110) == "상회"
    assert index_band(90) == "하회"
    assert index_band(100) == "비슷"
    assert index_band(109) == "비슷"
    assert index_band(None) is None


# ── Fact / DemandSignal 자동 유도 ───────────────────────────────────────────
def test_fact_auto_index() -> None:
    f = Fact(item="고령인구비율", value=22.1, national_avg=19.5, unit="%",
             source_tbl="DT_1B04005N", year=2025, scope="영등포구", scope_level="시군구")
    assert f.index == 113 and f.index_band == "상회"


def test_fact_count_no_index() -> None:
    g = Fact(item="총인구수", value=34066, national_avg=51000000, unit="명",
             source_tbl="DT", year=2025)
    assert g.index is None and g.index_band is None


def test_fact_explicit_index_respected() -> None:
    f = Fact(item="x", value=1, national_avg=1, unit="%", source_tbl="t", year=2025, index=999)
    assert f.index == 999  # 명시값 존중 (band는 999→상회 파생)
    assert f.index_band == "상회"


def test_demand_signal_auto_index() -> None:
    d = DemandSignal(item="유소년인구비율", value=8.3, national_avg=10.3, unit="%",
                     level="낮음", source_tbl="DT", year=2025, scope="영등포구", scope_level="시군구")
    assert d.index == 81 and d.index_band == "하회"
