"""T5 — 방법론·데이터 부록 엔진 테스트 (네트워크 불필요).

build_methodology 가 BoardResult 에 실제로 흐른 출처만 모으고(no silent inclusion),
동적 식별자(에어코리아-종로구·SGIS 집계구)를 정규화하며, 등장한 산정식·한계만 각인하는지 검증.
LLM 0·새 숫자 0 — 순수 메타데이터 조인. 미등록 출처는 지어내지 않음 (절대 원칙 3).
"""

from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.board import DomainCoverage
from app.schemas.diagnose import DemandSignal, Diagnosis, SupplySignal
from app.schemas.project_seed import Site
from app.schemas.region import Fact, Region
from app.schemas.site import BuildingInfo, HazardZone, LandPrice, SiteHazards
from app.services.methodology import build_methodology


def _f(item, value=20.0, national=15.0, unit="%", tbl="DT_1B04005N", stype="kosis",
       scope_level="시군구", year=2025):
    return Fact(item=item, value=value, national_avg=national, unit=unit, source_tbl=tbl,
                source_type=stype, year=year, scope="영등포구", scope_level=scope_level)


def _board(**over):
    base = dict(facts=[], diagnoses=[], resolution="시군구", base_date="2026-07-09",
                hazards=None, land_price=None, building=None, real_estate=None,
                context=None, coverage=[])
    base.update(over)
    return SimpleNamespace(**base)


def _diag(density_basis="", demand_scope="시군구"):
    return Diagnosis(
        name="의료시설 수급",
        demand=DemandSignal(item="고령인구비율", value=22.1, national_avg=19.5, unit="%",
                            level="높음", source_tbl="DT_1B04005N", year=2025,
                            scope="영등포구", scope_level=demand_scope),
        supply=SupplySignal(kinds=["병원"], count=4, radius=1000, level="적음",
                            density_basis=density_basis),
        signal="", note="", tag="참고")


# ── 출처 매핑 ────────────────────────────────────────────────────────────────
def test_kosis_source_mapped_by_tblid() -> None:
    m = build_methodology(_board(facts=[_f("고령인구비율"),
                                        _f("총인구수", unit="명", national=None)]))
    src = {s.key: s for s in m.sources}
    assert "DT_1B04005N" in src
    s = src["DT_1B04005N"]
    assert s.publisher == "통계청 KOSIS" and s.kind == "통계표"
    assert "고령인구비율" in s.used_for and "총인구수" in s.used_for  # 실제 기여 지표
    assert s.years == [2025]
    assert s.proximity == "시군구"


def test_dynamic_prefix_airkorea_and_sgis() -> None:
    facts = [_f("PM2.5 (초미세먼지)", unit="㎍/㎥", tbl="에어코리아-종로구", stype="airkorea"),
             _f("유소년인구비율", tbl="SGIS 집계구", stype=None, scope_level="반경")]
    m = build_methodology(_board(facts=facts, resolution="반경"))
    keys = {s.key for s in m.sources}
    assert "에어코리아" in keys          # source_tbl 접두 매칭
    assert "SGIS 집계구" in keys
    ak = next(s for s in m.sources if s.key == "에어코리아")
    assert ak.publisher.startswith("한국환경공단")
    sg = next(s for s in m.sources if s.key == "SGIS 집계구")
    assert sg.proximity == "반경"        # 최상급 근접도


def test_presence_sources_only_when_present() -> None:
    b = _board(
        facts=[_f("고령인구비율")],
        hazards=SiteHazards(flood=HazardZone(in_zone=True), landslide=HazardZone(in_zone=False)),
        land_price=LandPrice(price_per_sqm=29793000, year=2025),
        building=BuildingInfo(name="에프케이아이타워"),
        context={"stores": {"total": 10}, "schools": None, "notes": []},
    )
    keys = {s.key for s in build_methodology(b).sources}
    assert {"SGIS 재해위험지도", "VWorld 개별공시지가", "건축HUB 건축물대장",
            "상가(상권)정보"} <= keys
    assert "NEIS 학교" not in keys        # schools=None → 미포함 (no silent inclusion)
    assert "KOPIS 공연시설" not in keys   # 아예 없음


def test_unregistered_source_falls_back_honestly() -> None:
    m = build_methodology(_board(facts=[_f("이상한지표", tbl="UNKNOWN_TBL", stype="weird")]))
    s = next(s for s in m.sources if s.key == "UNKNOWN_TBL")
    assert "미등록" in s.note
    assert s.name == "UNKNOWN_TBL"        # 지어내지 않음 (절대 원칙 3)


# ── 산정식 ──────────────────────────────────────────────────────────────────
def test_formulas_derived_index_and_radius() -> None:
    facts = [_f("고령인구비율"), _f("1인가구비율", tbl="DT_1JC1511")]
    items = {f.item for f in build_methodology(_board(facts=facts)).formulas}
    assert {"고령인구비율", "1인가구비율", "전국=100 지수"} <= items
    assert "반경 인구" not in items       # 시군구 모드
    items2 = {f.item for f in build_methodology(_board(facts=facts, resolution="반경")).formulas}
    assert {"반경 인구", "반경 연령비율"} <= items2


def test_density_formula_when_radius_supply() -> None:
    m = build_methodology(_board(diagnoses=[_diag(density_basis="반경", demand_scope="반경")]))
    assert "공급 밀도(만명당)" in {f.item for f in m.formulas}
    assert "DT_1B04005N" in {s.key for s in m.sources}  # 수요 source 도 집계
    # 개수 판정(구/동 모드)이면 밀도 산정식 없음
    m2 = build_methodology(_board(diagnoses=[_diag(density_basis="")]))
    assert "공급 밀도(만명당)" not in {f.item for f in m2.formulas}


def test_demand_only_indicator_formula_included() -> None:
    # 문화시설 수급의 수요 proxy(생산가능인구비율)는 facts 엔 없지만 산정식은 각인돼야 함
    d = Diagnosis(
        name="문화시설 수급",
        demand=DemandSignal(item="생산가능인구비율", value=72.5, national_avg=70.1, unit="%",
                            level="비슷", source_tbl="SGIS 집계구", year=2023, scope_level="반경"),
        supply=SupplySignal(kinds=["도서관"], count=8, radius=1000, level="많음"),
        signal="", note="", tag="참고")
    m = build_methodology(_board(diagnoses=[d]))
    assert "생산가능인구비율" in {f.item for f in m.formulas}
    assert "전국=100 지수" in {f.item for f in m.formulas}  # demand.index 로도 발화


# ── 한계 ────────────────────────────────────────────────────────────────────
def test_limitations_caveat_coverage_heuristic() -> None:
    cov = [DomainCoverage(domain="재해", available=False, detail="확인 불가"),
           DomainCoverage(domain="인구", available=True, detail="1개 지표")]
    m = build_methodology(_board(facts=[_f("고령인구비율")], diagnoses=[_diag()], coverage=cov))
    joined = " ".join(m.limitations)
    assert "시군구 평균" in joined
    assert "재해 도메인 확인 불가" in joined
    assert "휴리스틱" in joined


def test_empty_board_no_silent_inclusion() -> None:
    m = build_methodology(_board())
    assert m.sources == [] and m.formulas == []
    assert "시군구 평균" in " ".join(m.limitations)  # 캐비엇은 항상
    assert m.resolution == "시군구"


# ── /board 통합 — 부록이 실제로 붙는지 ────────────────────────────────────────
client = TestClient(app)


def test_board_endpoint_attaches_methodology(monkeypatch) -> None:
    site = Site(address="서울 영등포구 여의대로 24", lat=37.52, lon=126.92, pnu="1156011000",
                bcode="1156010000", sgg_code="11560", sido="서울", sigungu="영등포구",
                eupmyeondong="여의동")
    analyze = SimpleNamespace(
        facts=[_f("고령인구비율", 22.1, 19.5)],
        implications=[], region=Region(name="영등포구", code="11560", resolution="시군구"), notes=[])
    monkeypatch.setattr("app.routers.board.build_site", lambda *a, **k: site)
    monkeypatch.setattr("app.routers.board.build_diagnosis",
                        lambda *a, **k: SimpleNamespace(diagnoses=[], notes=[]))
    monkeypatch.setattr("app.routers.analyze.analyze", lambda *a, **k: analyze)
    monkeypatch.setattr("app.routers.site.site_info",
                        lambda *a, **k: SimpleNamespace(hazards=None, land_price=None,
                                                        building=None, real_estate=None, notes=[]))
    monkeypatch.setattr("app.routers.seed.seed",
                        lambda *a, **k: SimpleNamespace(context={"notes": []}))

    b = client.post("/board", json={"address": "x", "use_type": "주거"}).json()
    assert b["methodology"] is not None
    m = b["methodology"]
    assert m["resolution"] == "시군구"
    assert "DT_1B04005N" in {s["key"] for s in m["sources"]}
    assert m["summary"] and m["limitations"]
