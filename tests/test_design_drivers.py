"""T2 — 설계 드라이버 합성 단위테스트 (네트워크 불필요).

증거 강도 랭킹·상위 N·근거 인용(값+근접도)·use_type 필터·게이팅을 결정적으로 검증한다.
strength 는 기존 값(지수·수준·in_zone)의 가중합일 뿐 — 새 숫자 없음 (절대 원칙 1·2).
"""

from __future__ import annotations

from app.schemas.diagnose import Diagnosis, DemandSignal, SupplySignal
from app.schemas.region import Fact
from app.schemas.site import HazardExposure, HazardZone, SiteHazards
from app.services.design_drivers import derive_design_drivers


def _fact(item, value, national, unit="%", scope_level="시군구"):
    return Fact(item=item, value=value, national_avg=national, unit=unit,
                source_tbl="T", year=2025, scope="영등포구", scope_level=scope_level)


def _med_diag(level="적음"):
    return Diagnosis(
        name="의료시설 수급",
        demand=DemandSignal(item="고령인구비율", value=22.1, national_avg=19.5, unit="%",
                            level="높음", source_tbl="T", year=2025, scope="영등포구", scope_level="시군구"),
        supply=SupplySignal(kinds=["병원", "의원", "약국"], count=4, radius=1000, level=level),
        signal="", note="", tag="참고")


def _flood():
    return SiteHazards(
        dong_name="여의도동",
        flood=HazardZone(in_zone=True, exposure_scope="읍면동",
                         exposures=[HazardExposure(metric="지하건물", affected=71, unit="동")]),
        landslide=HazardZone(in_zone=False, exposure_scope="시군구"))


# ── 랭킹 순서·상위 N ─────────────────────────────────────────────────────────
def test_drivers_ranked_by_strength_and_capped() -> None:
    facts = [_fact("고령인구비율", 22.1, 19.5), _fact("1인가구비율", 40.0, 33.0),
             _fact("생산가능인구비율", 72.5, 68.5)]
    out = derive_design_drivers(facts, [_med_diag()], _flood(), use_type="주거")
    assert len(out) <= 3
    assert [d.rank for d in out] == list(range(1, len(out) + 1))
    # 강도 내림차순
    strengths = [d.strength for d in out]
    assert strengths == sorted(strengths, reverse=True)
    # 방재(홍수 3.0+지하 1.0=4.0)가 1순위
    assert out[0].name == "방재·침수 대비" and out[0].strength == 4.0


# ── 강도 산술 (지수·수급·근접도 가중합) ──────────────────────────────────────
def test_access_driver_strength_math() -> None:
    # 고령 지수 113 → 1.3×시군구(1.0) + 의료 공급 적음 2.0×반경(1.2)=2.4 → 3.7
    facts = [_fact("고령인구비율", 22.1, 19.5)]
    out = derive_design_drivers(facts, [_med_diag()], None, use_type="의료")
    acc = next(d for d in out if d.name == "접근성·무장애 동선")
    assert acc.strength == 3.7
    keys = {e.key: e for e in acc.evidence}
    assert "지수 113" in keys["고령인구비율"].detail
    assert keys["의료시설 수급(공급)"].proximity == "반경"


# ── 게이팅: dir high 는 상회일 때만 / 절대수는 기여 없음 ─────────────────────
def test_low_index_does_not_fire_high_driver() -> None:
    # 유소년 지수 81(하회) → 보육 드라이버(dir high) 미발화
    facts = [_fact("유소년인구비율", 8.3, 10.3)]
    out = derive_design_drivers(facts, [], None, use_type="주거")
    assert "보육·가족 인프라" not in {d.name for d in out}


def test_count_metric_contributes_nothing() -> None:
    # 총인구수(절대수)는 index None → 어떤 드라이버에도 기여 안 함
    facts = [_fact("총인구수", 34066, 51000000, unit="명")]
    assert derive_design_drivers(facts, [], None) == []


# ── use_type 필터 ────────────────────────────────────────────────────────────
def test_use_type_filter() -> None:
    facts = [_fact("고령인구비율", 22.1, 19.5)]
    # 접근성 use_types=[주거,의료,복지] → 상업이면 제외
    out = derive_design_drivers(facts, [_med_diag()], None, use_type="상업")
    assert "접근성·무장애 동선" not in {d.name for d in out}


# ── 빈 입력 ──────────────────────────────────────────────────────────────────
def test_empty_pool() -> None:
    assert derive_design_drivers() == []
    assert derive_design_drivers([], [], None) == []
