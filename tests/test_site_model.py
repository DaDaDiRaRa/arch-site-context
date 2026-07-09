"""arch-site-model 결합 테스트 (네트워크 불필요).

터읽기는 arch-site-model 을 호출하지 않는다(provider 경계) — assembler 가 넘긴 출력을
요약·렌더만 하는지 검증. summarize_model 압축·방어, 계약 model 슬롯, /board 배선,
축측 매싱 렌더, board_view 물리 모델 섹션. 새 숫자 0 (값은 arch-site-model 이 만든 그대로).
"""

from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.routers.board import _massing_anchor
from app.schemas.board import BoardResult
from app.schemas.project_seed import Site
from app.schemas.region import Fact, Region
from app.schemas.site_model import MAX_FOOTPRINTS, SiteModelSummary
from app.services.board_contract import board_to_project_seed
from app.services.board_view import render_board_html
from app.services.site_model import summarize_model

client = TestClient(app)


def _raw_model():
    """arch-site-model POST /api/generate 응답 (실제 형태 축약)."""
    return {
        "ok": True, "job_id": "abc123",
        "geometry": {
            "buildings": [
                {"footprint": [[0, 0], [10, 0], [10, 10], [0, 10]], "base_z": -0.5, "height": 12.0, "verified": True},
                {"footprint": [[20, 20], [35, 20], [35, 35], [20, 35]], "base_z": -0.3, "height": 30.0},
                {"footprint": [[5, 40]], "height": 9.0},  # 점 부족 → 미리보기에서 건너뜀
            ],
            "terrain": {"vertices": [[0, 0, 10]], "triangles": [[0, 0, 0]]},
            "cadastral": [{"pnu": "1156011000123456789", "ring": [[0, 0, 10]]}],
        },
        "files": {"3dm": "http://host/api/files/abc123/3dm", "ortho": "http://host/api/files/abc123/ortho"},
        "stats": {"buildings": 2, "solids": 2, "cadastral_parcels": 1, "terrain_triangles": 2467,
                  "elev_range_m": [35.2, 112.7], "origin_offset": [936142.5, 415678.2]},
        "provenance": {"building_src": "VWorld LT_C_SPBD", "radius_m": 250, "fetched_at": "2026-07-09T12:34:56+00:00"},
        "warnings": ["건물 3개는 gro_flo_co 누락 → 기본 1층 적용"],
    }


def _min_board(**over):
    base = dict(
        site=Site(address="서울 영등포구 여의대로 24", lat=37.52, lon=126.92, pnu="1156011000",
                  sgg_code="11560", sido="서울", sigungu="영등포구", eupmyeondong="여의도동"),
        use_type="주거", radius=1000, resolution="시군구", base_date="2026-07-09",
    )
    base.update(over)
    return BoardResult(**base)


# ── 요약 추출 ────────────────────────────────────────────────────────────────
def test_summarize_extracts_compact() -> None:
    m = summarize_model(_raw_model())
    assert m.building_count == 2 and m.solids == 2 and m.cadastral_parcels == 1
    assert m.elev_range_m == [35.2, 112.7]
    assert m.origin_offset == [936142.5, 415678.2]  # 좌표 복원용 보존
    assert m.radius_m == 250
    assert len(m.footprints) == 2  # 점 부족 건물은 건너뜀
    assert m.heights_m == [12.0, 30.0]
    assert m.files["3dm"].startswith("http")
    assert m.provenance["building_src"] == "VWorld LT_C_SPBD"
    assert m.warnings and "gro_flo_co" in m.warnings[0]


def test_summarize_none_and_empty() -> None:
    assert summarize_model(None) is None
    assert summarize_model("nope") is None
    assert summarize_model({}) is None  # 신호 0 → None (no silent empty)
    # 통계만 있어도(geometry 없이) 요약 — 건물 미리보기는 빈 목록
    m = summarize_model({"stats": {"buildings": 5}})
    assert m is not None and m.building_count == 5 and m.footprints == []


def test_summarize_truncates_and_keeps_full_stats() -> None:
    many = {"geometry": {"buildings": [{"footprint": [[0, 0], [1, 0], [1, 1]], "height": 3.0}
                                       for _ in range(MAX_FOOTPRINTS + 5)]},
            "stats": {"buildings": MAX_FOOTPRINTS + 5}}
    m = summarize_model(many)
    assert len(m.footprints) == MAX_FOOTPRINTS       # 미리보기 상한
    assert m.building_count == MAX_FOOTPRINTS + 5     # 통계는 전체 기준
    assert "생략" in m.note


# ── 계약 model 슬롯 ──────────────────────────────────────────────────────────
def test_project_seed_model_slot() -> None:
    raw = {"geometry": {"buildings": []}, "stats": {"buildings": 3}}
    seed = board_to_project_seed(_min_board(), model=raw)
    assert seed.model == raw          # 형제앱 자리 — 느슨한 dict 그대로
    assert seed.law is None and seed.knowledge is None


# ── /board 배선 (assembler 가 model 넘김 → BoardResult.model 요약) ────────────
def test_board_endpoint_summarizes_passed_model(monkeypatch) -> None:
    site = Site(address="x", lat=37.52, lon=126.92, pnu="1156011000", sgg_code="11560",
                sido="서울", sigungu="영등포구", eupmyeondong="여의동")
    analyze = SimpleNamespace(facts=[Fact(item="고령인구비율", value=22.1, national_avg=19.5, unit="%",
                                          source_tbl="DT_1B04005N", year=2025, scope="영등포구", scope_level="시군구")],
                              implications=[], region=Region(name="영등포구", code="11560", resolution="시군구"), notes=[])
    monkeypatch.setattr("app.routers.board.build_site", lambda *a, **k: site)
    monkeypatch.setattr("app.routers.board.build_diagnosis", lambda *a, **k: SimpleNamespace(diagnoses=[], notes=[]))
    monkeypatch.setattr("app.routers.analyze.analyze", lambda *a, **k: analyze)
    monkeypatch.setattr("app.routers.site.site_info",
                        lambda *a, **k: SimpleNamespace(hazards=None, land_price=None, building=None, real_estate=None, notes=[]))
    monkeypatch.setattr("app.routers.seed.seed", lambda *a, **k: SimpleNamespace(context={"notes": []}))

    # model 없으면 None
    b0 = client.post("/board", json={"address": "x", "use_type": "주거"}).json()
    assert b0["model"] is None
    # model 넘기면 요약 배선
    b1 = client.post("/board", json={"address": "x", "use_type": "주거", "model": _raw_model()}).json()
    assert b1["model"] is not None
    assert b1["model"]["building_count"] == 2
    assert b1["model"]["origin_offset"] == [936142.5, 415678.2]


# ── 축측 매싱 렌더 ────────────────────────────────────────────────────────────
def test_massing_anchor_renders_and_graceful() -> None:
    uri = _massing_anchor(summarize_model(_raw_model()))
    assert uri and uri.startswith("data:image/jpeg;base64,")
    # footprints 없으면 None (graceful)
    assert _massing_anchor(summarize_model({"stats": {"buildings": 1}})) is None


# ── board_view 물리 모델 섹션 ────────────────────────────────────────────────
def test_board_view_renders_model_section() -> None:
    b = _min_board(model=summarize_model(_raw_model()))
    html = render_board_html(b.model_dump(), massing_data_uri="data:image/jpeg;base64,ZZZZ")
    assert "물리 모델" in html
    assert 'src="data:image/jpeg;base64,ZZZZ"' in html
    assert "건물 2동" in html
    assert "표고 35~113m" in html          # 반올림 표기
    assert 'href="http://host/api/files/abc123/3dm"' in html  # 다운로드 링크


def test_board_view_no_model_section_when_absent() -> None:
    html = render_board_html(_min_board().model_dump())
    assert "물리 모델" not in html
