"""S4 — 종합 산출 두 블록 테스트 (네트워크 불필요).

Claude 호출 없이(키 제거) 결정적으로 검증: 그라운딩 없으면 no_data(환각 금지), 폴백 시
①은 실제 fact 로 서술·②는 '판단 유보'(가짜 의견 안 만듦), 라벨은 코드가 항상 부착.
그라운딩 텍스트에 근접도·출처가 실리는지도 확인 (절대 원칙 1·3·4).
"""

from __future__ import annotations

from app.schemas.diagnose import Diagnosis, DemandSignal, SupplySignal
from app.schemas.region import Fact
from app.services import synthesis
from app.services.synthesis import (
    JUDGMENT_LABEL,
    _pool_text,
    _rule_judgment,
    synthesize,
)


def _facts():
    return [Fact(item="고령인구비율", value=22.1, national_avg=19.5, unit="%",
                 source_tbl="DT_1B04005N", year=2025, scope="영등포구", scope_level="시군구")]


def _diags():
    return [Diagnosis(
        name="의료시설 수급",
        demand=DemandSignal(item="고령인구비율", value=22.1, national_avg=19.5, unit="%",
                            level="높음", source_tbl="DT", year=2025, scope="영등포구", scope_level="시군구"),
        supply=SupplySignal(kinds=["병원"], count=4, radius=1000, level="적음"),
        signal="수요 높음·공급 적음", note="", tag="참고")]


# ── 그라운딩 없음 → no_data (환각 금지) ─────────────────────────────────────
def test_no_grounding_returns_no_data() -> None:
    s = synthesize("주거", [], [], None, [])
    assert s.interpretation_source == "no_data"
    assert s.judgment_source == "no_data"
    assert s.judgment_label == JUDGMENT_LABEL


# ── 키 없음 → 규칙 폴백 (①은 fact 서술, ②는 판단 유보) ──────────────────────
def test_rule_fallback_without_key(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    s = synthesize("주거", _facts(), _diags(), None, [])

    assert s.interpretation_source == "rule_based_fallback"
    assert s.interpretation_model == ""
    # ① 은 실제 수치를 담는다 (새 숫자 없음, 원본 그대로)
    assert "22.1" in s.interpretation and "19.5" in s.interpretation
    # 공급 적음 항목이 언급됨
    assert "의료시설 수급" in s.interpretation

    # ② 는 가짜 의견을 만들지 않고 '판단 유보'
    assert s.judgment_source == "rule_based_fallback"
    assert "판단" in s.judgment
    assert s.judgment_label == JUDGMENT_LABEL


def test_rule_judgment_does_not_fabricate() -> None:
    # ② 폴백은 구체 금액·수익·적합 단정을 만들지 않는다
    txt = _rule_judgment()
    for banned in ("억", "수익률", "적합합니다", "추천"):
        assert banned not in txt


# ── 그라운딩 텍스트에 근접도·출처 포함 (절대 원칙 4) ─────────────────────────
def test_pool_text_carries_proximity_and_source() -> None:
    txt = _pool_text(_facts(), _diags(), None, [])
    assert "근접도 시군구" in txt
    assert "DT_1B04005N" in txt
    assert "의료시설 수급" in txt


def test_has_grounding_detects_hazard_only(monkeypatch) -> None:
    # facts 없어도 재해 in_zone 이 있으면 그라운딩 있음 → no_data 아님
    from app.schemas.site import SiteHazards, HazardZone
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    hz = SiteHazards(flood=HazardZone(in_zone=True), landslide=HazardZone(in_zone=False))
    s = synthesize("주거", [], [], hz, [])
    assert s.interpretation_source == "rule_based_fallback"  # no_data 아님
