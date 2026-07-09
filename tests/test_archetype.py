"""T1.5 — 대지 아키타입 분류 단위테스트 (네트워크 불필요).

규칙 룩업으로 지배 유형 1개(+alternatives)를 라벨링. 새 숫자 없음 — 지수·값·in_zone 조합만.
풀 없으면 None(확인불가), 강한 매칭 없으면 '혼합형' 폴백(억지 분류 금지). K-means 아님.
"""

from __future__ import annotations

from app.schemas.region import Fact
from app.schemas.site import HazardZone, SiteHazards
from app.services.archetype import classify_archetype


def _f(item, value, national, unit="%"):
    return Fact(item=item, value=value, national_avg=national, unit=unit,
                source_tbl="T", year=2025, scope="영등포구", scope_level="시군구")


def test_single_household_urban_primary() -> None:
    facts = [_f("1인가구비율", 45.1, 36.1), _f("평균가구원수", 2.0, 2.2, unit="명"),
             _f("순이동", -3151.0, 0.0, unit="명")]
    hz = SiteHazards(flood=HazardZone(in_zone=True, exposure_scope="읍면동"),
                     landslide=HazardZone(in_zone=True, exposure_scope="시군구"))
    a = classify_archetype(facts, [], hz, use_type="주거")
    assert a.name == "1인가구 도심 임대권" and a.group == "주거·1인"
    assert a.match_score == 2.0  # 두 signal 매칭
    keys = {e.key for e in a.evidence}
    assert "1인가구비율" in keys and "평균가구원수" in keys
    # 차점 특성 (침수·유출 등)
    assert "저지대 침수 민감지" in a.alternatives or "인구 유출 관망지" in a.alternatives


def test_aged_settled_via_low_youth() -> None:
    # 고령 high + 유소년 low → 고령 정주형 (dir low 게이팅)
    facts = [_f("고령인구비율", 27.0, 21.2), _f("유소년인구비율", 7.0, 10.3)]
    a = classify_archetype(facts, [], None, use_type="주거")
    assert a.name == "고령 정주형 주거지" and a.match_score == 2.0


def test_empty_pool_none() -> None:
    assert classify_archetype([], [], None) is None


def test_weak_match_falls_back_to_mixed() -> None:
    # 지수 없는 절대수만 → 어떤 유형도 매칭 못함 → 혼합형 폴백 (억지 분류 금지)
    a = classify_archetype([_f("총인구수", 100, 100, unit="명")], [], None)
    assert a is not None and a.name == "혼합형 시가지" and a.match_score == 0.0


def test_min_match_gates_multi_signal_type() -> None:
    # 생산연령 밀집(min_match 2): 생산가능 high 만 있고 인구밀도 없음 → 미채택
    facts = [_f("생산가능인구비율", 78.0, 71.0)]
    a = classify_archetype(facts, [], None)
    assert a.name != "생산연령 밀집 도심"  # 폴백 또는 타 유형


def test_hazard_only_classifies() -> None:
    hz = SiteHazards(flood=HazardZone(in_zone=True, exposure_scope="읍면동"),
                     landslide=HazardZone(in_zone=False, exposure_scope="시군구"))
    a = classify_archetype([], [], hz)
    assert a.name == "저지대 침수 민감지"
    assert a.evidence[0].key == "홍수 위험"
