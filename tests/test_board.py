"""S3 — /board 통합 진입점 테스트 (네트워크 불필요, monkeypatch).

/board 는 오케스트레이션만 — 기존 서비스(analyze·diagnose·site·seed)를 가짜로 대체하고,
그 위에서 **실제 S2 엔진**(cross_context.json)이 도는지 + coverage(결측 투명)·notes 병합 +
부분 실패 격리를 검증한다. 데이터·숫자는 만들지 않는다 (절대 원칙 1·3).
"""

from __future__ import annotations

from types import SimpleNamespace

from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.diagnose import Diagnosis, DemandSignal, SupplySignal
from app.schemas.project_seed import Site
from app.schemas.region import Fact, Implication, Region
from app.schemas.site import (
    BuildingInfo,
    HazardExposure,
    HazardZone,
    LandPrice,
    SiteHazards,
)

client = TestClient(app)


def _site():
    return Site(address="서울 영등포구 여의대로 24", lat=37.52, lon=126.92,
                pnu="1156011000", bcode="1156010000", sgg_code="11560",
                sido="서울", sigungu="영등포구", eupmyeondong="여의동")


def _analyze_ok():
    return SimpleNamespace(
        facts=[Fact(item="고령인구비율", value=22.1, national_avg=19.5, unit="%",
                    source_tbl="DT_1B04005N", year=2025, scope="영등포구", scope_level="시군구")],
        implications=[Implication(text="무장애 동선 검토", basis="고령인구비율", tag="참고")],
        region=Region(name="영등포구", code="11560", resolution="시군구"),
        notes=["분석 단위: 시군구"],
    )


def _diagnose_ok():
    d = Diagnosis(
        name="의료시설 수급",
        demand=DemandSignal(item="고령인구비율", value=22.1, national_avg=19.5, unit="%",
                            level="높음", source_tbl="DT_1B04005N", year=2025,
                            scope="영등포구", scope_level="시군구"),
        supply=SupplySignal(kinds=["병원", "의원", "약국"], count=4, radius=1000, level="적음"),
        signal="수요 높음·공급 적음", note="...", tag="참고",
    )
    return SimpleNamespace(diagnoses=[d], notes=["수급진단 note"])


def _site_ok():
    hz = SiteHazards(
        dong_name="여의도동",
        flood=HazardZone(in_zone=True, exposure_scope="읍면동",
                         exposures=[HazardExposure(metric="지하건물", affected=71, total=100, unit="동")]),
        landslide=HazardZone(in_zone=False, exposure_scope="시군구"),
    )
    return SimpleNamespace(
        hazards=hz,
        land_price=LandPrice(price_per_sqm=29793000, year=2025, pnu="1156011000",
                             addr="", jibun="", note=""),
        building=BuildingInfo(name="에프케이아이타워", bcr=52.75, far=940.36, note=""),
        real_estate=None,
        notes=["대지 note"],
    )


def _seed_ok():
    return SimpleNamespace(context={"stores": {"total": 100}, "schools": None,
                                    "notes": ["학교: 미확보"]})


def _patch_all(monkeypatch, analyze=_analyze_ok, diagnose=_diagnose_ok,
               site=_site_ok, seed=_seed_ok, build_site=_site):
    monkeypatch.setattr("app.routers.board.build_site", lambda *a, **k: build_site())
    monkeypatch.setattr("app.routers.board.build_diagnosis", lambda *a, **k: diagnose())
    monkeypatch.setattr("app.routers.analyze.analyze", lambda *a, **k: analyze())
    monkeypatch.setattr("app.routers.site.site_info", lambda *a, **k: site())
    monkeypatch.setattr("app.routers.seed.seed", lambda *a, **k: seed())


# ── 정상 조립 + 실제 S2 발화 ─────────────────────────────────────────────────
def test_board_assembles_and_fires_cross_rules(monkeypatch) -> None:
    _patch_all(monkeypatch)
    r = client.post("/board", json={"address": "서울 영등포구 여의대로 24",
                                    "use_type": "주거", "radius": 1000})
    assert r.status_code == 200
    b = r.json()

    # 조각들이 그대로 담김
    assert len(b["facts"]) == 1 and b["facts"][0]["proximity"] == "시군구"
    assert len(b["diagnoses"]) == 1
    assert b["hazards"]["flood"]["in_zone"] is True
    assert b["land_price"]["price_per_sqm"] == 29793000

    # ★ 실제 S2 엔진이 통합 풀에서 두 규칙 발화 (고령×의료 적음, 홍수×지하건물)
    names = {c["name"] for c in b["cross_implications"]}
    assert "의료 접근성" in names
    assert "지하 침수 대비" in names
    med = next(c for c in b["cross_implications"] if c["name"] == "의료 접근성")
    assert med["domains"] == ["인구", "수급"]
    assert any(bs["proximity"] == "반경" for bs in med["basis"])  # 공급 근거는 반경


def test_board_coverage_all_available(monkeypatch) -> None:
    _patch_all(monkeypatch)
    r = client.post("/board", json={"address": "x", "use_type": "주거"})
    cov = {c["domain"]: c for c in r.json()["coverage"]}
    assert set(cov) == {"인구", "수급", "재해", "대지", "생활맥락"}
    assert cov["인구"]["available"] and cov["수급"]["available"]
    assert cov["재해"]["available"] and "홍수 영향범위 포함" in cov["재해"]["detail"]
    assert cov["대지"]["available"]
    assert cov["생활맥락"]["available"]  # stores 있음


# ── 부분 실패 격리 (analyze 에러 → 인구만 결측, 보드는 200) ──────────────────
def test_board_isolates_analyze_failure(monkeypatch) -> None:
    def _analyze_err():
        return JSONResponse(status_code=422,
                            content={"code": "NO_DATA", "message": "확인 불가(용도)"})
    _patch_all(monkeypatch, analyze=_analyze_err)
    r = client.post("/board", json={"address": "x", "use_type": "주거"})
    assert r.status_code == 200
    b = r.json()
    assert b["facts"] == []
    cov = {c["domain"]: c for c in b["coverage"]}
    assert cov["인구"]["available"] is False
    # 에러 message 가 notes 로 정직하게 옮겨짐 (no silent skip)
    assert any("확인 불가(용도)" in n for n in b["notes"])
    # 인구 없어도 재해 규칙(지하 침수)은 여전히 발화
    assert "지하 침수 대비" in {c["name"] for c in b["cross_implications"]}


# ── S4 synthesize 플래그 배선 (synthesis 서비스는 stub) ──────────────────────
def test_board_synthesize_flag_wires_synthesis(monkeypatch) -> None:
    from app.schemas.board import Synthesis
    _patch_all(monkeypatch)

    def _stub(*a, **k):
        return Synthesis(
            interpretation="① 서술", interpretation_source="ai", interpretation_model="claude-sonnet-5",
            judgment="② 의견", judgment_source="ai", judgment_model="claude-opus-4-8",
            judgment_label="AI 의견 라벨",
        )
    monkeypatch.setattr("app.services.synthesis.synthesize", _stub)

    # 기본(off)이면 synthesis 없음
    r0 = client.post("/board", json={"address": "x", "use_type": "주거"})
    assert r0.json()["synthesis"] is None

    # synthesize=true 면 두 블록 배선
    r1 = client.post("/board", json={"address": "x", "use_type": "주거", "synthesize": True})
    syn = r1.json()["synthesis"]
    assert syn["interpretation"] == "① 서술"
    assert syn["judgment_model"] == "claude-opus-4-8"
    assert syn["judgment_label"] == "AI 의견 라벨"


# ── B4: 결과 캐시 — 같은 요청은 브랜치·Claude 재실행 없이 재사용 ──────────────
def test_board_caches_and_reuses(monkeypatch) -> None:
    calls = {"n": 0}

    def _diag_counting():
        calls["n"] += 1
        return _diagnose_ok()

    _patch_all(monkeypatch, diagnose=_diag_counting)
    body = {"address": "서울 영등포구 여의대로 24", "use_type": "주거", "radius": 1000}

    assert client.post("/board", json=body).status_code == 200
    assert calls["n"] == 1
    # 두 번째 동일 요청 → 캐시 히트 (브랜치 재실행 안 함) — /board/view 가 이 이득을 봄
    assert client.post("/board", json=body).status_code == 200
    assert calls["n"] == 1
    # 다른 파라미터(radius) → 캐시 미스 → 재계산
    assert client.post("/board", json={**body, "radius": 2000}).status_code == 200
    assert calls["n"] == 2


def test_board_cache_expires(monkeypatch) -> None:
    from app.routers import board as board_mod
    calls = {"n": 0}

    def _diag_counting():
        calls["n"] += 1
        return _diagnose_ok()

    _patch_all(monkeypatch, diagnose=_diag_counting)
    body = {"address": "x", "use_type": "주거"}
    assert client.post("/board", json=body).status_code == 200
    assert calls["n"] == 1
    # TTL 지난 것처럼 타임스탬프를 과거로 → 다음 호출은 재계산
    key = next(iter(board_mod._BOARD_CACHE))
    _ts, val = board_mod._BOARD_CACHE[key]
    board_mod._BOARD_CACHE[key] = (_ts - board_mod._BOARD_TTL - 1, val)
    assert client.post("/board", json=body).status_code == 200
    assert calls["n"] == 2


# ── 주소 해석 실패 = 하드블록 ────────────────────────────────────────────────
def test_board_bad_address_hard_blocks(monkeypatch) -> None:
    from app.services.kakao import KakaoError

    def _boom(*a, **k):
        raise KakaoError("no result")
    monkeypatch.setattr("app.routers.board.build_site", _boom)
    r = client.post("/board", json={"address": "없는주소", "use_type": "주거"})
    assert r.status_code == 422
    assert r.json()["code"] == "ADDR_UNRESOLVED"
