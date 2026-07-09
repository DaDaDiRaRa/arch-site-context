"""S2 — 교차규칙 엔진 단위테스트 (네트워크 불필요).

실제 객체 형태(Fact·Diagnosis·SiteHazards)로 3가지 대표 시사점 + 절별 경계·필터를 검증한다.
엔진은 boolean 조합·인용만 — 새 숫자 없음 (절대 원칙 1·2). 확인 불가(national_avg None 등)면
발화 안 함 (절대 원칙 3). 각 basis 에 S1 근접도가 실리는지 확인 (절대 원칙 4).
"""

from __future__ import annotations

from app.schemas.diagnose import Diagnosis, DemandSignal, SupplySignal
from app.schemas.region import Fact
from app.schemas.site import HazardExposure, HazardZone, HeatwaveHistory, SiteHazards
from app.services.cross_context import derive_cross_context


# ── 픽스처 헬퍼 ──────────────────────────────────────────────────────────────
def _fact(item, value, national=None, unit="%", scope_level="시군구"):
    return Fact(item=item, value=value, national_avg=national, unit=unit,
                source_tbl="T", year=2025, scope="영등포구", scope_level=scope_level)


def _diag(name, supply_level="보통", demand_level="평이", kinds=("병원",), count=5):
    return Diagnosis(
        name=name,
        demand=DemandSignal(item="고령인구비율", value=22.1, national_avg=19.5, unit="%",
                            level=demand_level, source_tbl="T", year=2025,
                            scope="영등포구", scope_level="시군구"),
        supply=SupplySignal(kinds=list(kinds), count=count, radius=1000, level=supply_level),
        signal=f"수요 {demand_level}·공급 {supply_level}", note="", tag="참고",
    )


def _hazards(flood_in=None, landslide_in=None, exposures=None, alert=0):
    return SiteHazards(
        dong_name="여의도동",
        flood=HazardZone(in_zone=flood_in, exposures=exposures or [], exposure_scope="읍면동"),
        landslide=HazardZone(in_zone=landslide_in, exposure_scope="시군구"),
        heatwave=HeatwaveHistory(alert_count=alert, warning_count=0, scope="서울 광역(권역)"),
    )


# ── 대표 시사점 1: 인구 × 수급 ───────────────────────────────────────────────
def test_medical_access_fires_on_aged_and_low_supply() -> None:
    facts = [_fact("고령인구비율", 22.1, 19.5)]           # 22.1 > 19.5+2 ✓
    diags = [_diag("의료시설 수급", supply_level="적음")]  # 공급 적음 ✓
    out = derive_cross_context(facts, diags, None, use_type="주거")
    names = {c.name for c in out}
    assert "의료 접근성" in names
    imp = next(c for c in out if c.name == "의료 접근성")
    assert imp.domains == ["인구", "수급"]
    assert imp.tag == "참고"
    # basis 에 값 그대로 인용 + S1 근접도
    keys = {b.key: b for b in imp.basis}
    assert keys["고령인구비율"].proximity == "시군구"
    assert "22.1" in keys["고령인구비율"].detail and "19.5" in keys["고령인구비율"].detail
    assert keys["의료시설 수급(공급)"].proximity == "반경"  # 공급은 반경 실측


def test_medical_access_silent_when_supply_not_low() -> None:
    facts = [_fact("고령인구비율", 22.1, 19.5)]
    diags = [_diag("의료시설 수급", supply_level="많음")]   # 공급 적음 아님 → 미발화
    out = derive_cross_context(facts, diags, None)
    assert "의료 접근성" not in {c.name for c in out}


def test_no_national_avg_does_not_fire() -> None:
    # 비교 기준 없으면 추정 않고 멈춤 (절대 원칙 3)
    facts = [_fact("고령인구비율", 22.1, None)]
    diags = [_diag("의료시설 수급", supply_level="적음")]
    out = derive_cross_context(facts, diags, None)
    assert "의료 접근성" not in {c.name for c in out}


# ── 대표 시사점 2: 재해 × 재해 (지하 침수) ──────────────────────────────────
def test_basement_flood_fires_on_zone_and_underground() -> None:
    hz = _hazards(flood_in=True, exposures=[
        HazardExposure(metric="지하건물", affected=71, total=100, unit="동"),
    ])
    out = derive_cross_context(hazards=hz)
    imp = next((c for c in out if c.name == "지하 침수 대비"), None)
    assert imp is not None
    assert imp.domains == ["재해"]
    detail = {b.key: b.detail for b in imp.basis}
    assert "홍수 위험" in detail
    assert "71" in detail["홍수 영향 지하건물"]


def test_basement_flood_silent_when_not_in_zone() -> None:
    hz = _hazards(flood_in=False, exposures=[
        HazardExposure(metric="지하건물", affected=71, unit="동"),
    ])
    out = derive_cross_context(hazards=hz)
    assert "지하 침수 대비" not in {c.name for c in out}


def test_compound_hazard_fires_on_both_zones() -> None:
    hz = _hazards(flood_in=True, landslide_in=True)
    out = derive_cross_context(hazards=hz)
    assert "복합 재해 노출" in {c.name for c in out}


# ── 대표 시사점 3: 인구 × 재해 (폭염) ───────────────────────────────────────
def test_heatwave_vulnerable_fires() -> None:
    facts = [_fact("1인가구비율", 40.0, 33.0)]   # 40 > 33+3 ✓
    hz = _hazards(alert=11)                        # 경보 11 >= 5 ✓
    out = derive_cross_context(facts, None, hz, use_type="주거")
    imp = next((c for c in out if c.name == "취약계층 폭염 대응"), None)
    assert imp is not None
    assert set(imp.domains) == {"인구", "재해"}
    # 광역 권역 폭염은 대지에서 먼 근사 → proxy
    hw_basis = next(b for b in imp.basis if b.key == "폭염경보")
    assert hw_basis.proximity == "proxy"


def test_heatwave_silent_below_threshold() -> None:
    facts = [_fact("1인가구비율", 40.0, 33.0)]
    hz = _hazards(alert=4)                          # 경보 4 < 5 → 미발화
    out = derive_cross_context(facts, None, hz)
    assert "취약계층 폭염 대응" not in {c.name for c in out}


# ── use_type 필터 ────────────────────────────────────────────────────────────
def test_use_type_filter_excludes_rule() -> None:
    facts = [_fact("고령인구비율", 22.1, 19.5)]
    diags = [_diag("의료시설 수급", supply_level="적음")]
    # 의료 접근성 use_types=[주거,의료,복지] → 상업이면 제외
    out = derive_cross_context(facts, diags, None, use_type="상업")
    assert "의료 접근성" not in {c.name for c in out}


# ── 빈 입력 graceful ─────────────────────────────────────────────────────────
def test_empty_pool_returns_empty() -> None:
    assert derive_cross_context() == []
    assert derive_cross_context([], [], None) == []
