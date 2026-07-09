"""T3 — 프로그램 함의(POR) 단위테스트 (네트워크 불필요).

when 절이 모두 참일 때만 카테고리별 권고 방출, 중복 병합, 카테고리 순 정렬을 검증한다.
절 매칭은 S2 cross_context._eval_clause 재사용 — LLM 0·새 숫자 0.
"""

from __future__ import annotations

from app.schemas.diagnose import Diagnosis, DemandSignal, SupplySignal
from app.schemas.region import Fact
from app.schemas.site import HazardExposure, HazardZone, SiteHazards
from app.services.program import derive_program


def _f(item, value, national, unit="%"):
    return Fact(item=item, value=value, national_avg=national, unit=unit,
                source_tbl="T", year=2025, scope="영등포구", scope_level="시군구")


def _med(level="적음"):
    return Diagnosis(
        name="의료시설 수급",
        demand=DemandSignal(item="고령인구비율", value=22.1, national_avg=19.5, unit="%",
                            level="높음", source_tbl="T", year=2025, scope="영등포구", scope_level="시군구"),
        supply=SupplySignal(kinds=["병원"], count=4, radius=1000, level=level),
        signal="", note="", tag="참고")


def test_single_household_program() -> None:
    items = derive_program([_f("1인가구비율", 45.1, 36.1)], [], None, use_type="주거")
    recs = {(i.category, i.recommendation) for i in items}
    assert ("평면·세대", "소형 평형 비중 상향 검토 (1인가구 대응)") in recs
    assert any(c == "공용부" for c, _ in recs)
    # 근거 부착
    assert all(i.basis for i in items)


def test_and_gating_requires_all_clauses() -> None:
    # 고령·의료 접근성은 고령 high AND 의료 공급 적음 — 공급 '많음'이면 미발화
    items = derive_program([_f("고령인구비율", 22.1, 19.5)], [_med(level="많음")], None, use_type="주거")
    assert not any("무장애 코어" in i.recommendation for i in items)
    items2 = derive_program([_f("고령인구비율", 22.1, 19.5)], [_med(level="적음")], None, use_type="주거")
    assert any("무장애 코어" in i.recommendation for i in items2)


def test_grouped_and_sorted_by_category() -> None:
    hz = SiteHazards(flood=HazardZone(in_zone=True, exposure_scope="읍면동"),
                     landslide=HazardZone(in_zone=False, exposure_scope="시군구"))
    items = derive_program([_f("1인가구비율", 45.1, 36.1)], [], hz, use_type="주거")
    cats = [i.category for i in items]
    # 카테고리 정렬 순서(대지·배치 먼저)를 따름 — 같은 카테고리는 인접
    order = {c: i for i, c in enumerate(["대지·배치", "저층부", "평면·세대", "코어·동선", "공용부", "방재·설비", "조경·외부"])}
    ranks = [order.get(c, 99) for c in cats]
    assert ranks == sorted(ranks)  # 그룹핑(카테고리 비내림차순)


def test_dedup_merges_basis() -> None:
    # 홍수 방재 규칙이 방재·설비/대지·배치 항목을 냄. 여러 규칙이 같은 항목 내면 basis 병합.
    hz = SiteHazards(flood=HazardZone(in_zone=True, exposure_scope="읍면동",
                     exposures=[HazardExposure(metric="노후건물", affected=52, unit="개")]),
                     landslide=HazardZone(in_zone=False, exposure_scope="시군구"))
    items = derive_program([], [], hz)
    # 같은 (category, recommendation) 은 한 번만
    keys = [(i.category, i.recommendation) for i in items]
    assert len(keys) == len(set(keys))


def test_empty_pool() -> None:
    assert derive_program([], [], None) == []
