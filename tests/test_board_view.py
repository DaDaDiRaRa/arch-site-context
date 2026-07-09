"""T4 — 대지분석 보드 렌더/내보내기 테스트 (네트워크 불필요).

render_board_html 이 자체완결 HTML(핵심 섹션·XSS-safe)을 내는지, /board/view 가 board 를
빌드해 파일로 저장하고 공유 URL 을 반환하는지 검증. 렌더는 기존 값을 그릴 뿐 — 새 데이터 0.
"""

from __future__ import annotations

from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.board import BoardResult, DomainCoverage, Synthesis
from app.schemas.design_drivers import DesignDriver, DriverEvidence
from app.schemas.project_seed import Site
from app.schemas.region import Fact
from app.services.board_view import render_board_html

client = TestClient(app)


def _board(**over):
    base = dict(
        site=Site(address="서울 영등포구 여의대로 24", lat=37.52, lon=126.92,
                  pnu="1156011000", sgg_code="11560", sido="서울",
                  sigungu="영등포구", eupmyeondong="여의도동"),
        use_type="주거", radius=1000, resolution="시군구",
        facts=[Fact(item="1인가구비율", value=45.1, national_avg=36.1, unit="%",
                    source_tbl="DT_1JC1511", year=2024, scope="영등포구", scope_level="시군구")],
        design_drivers=[DesignDriver(rank=1, name="방재·침수 대비", response="방수판·전기실 검토",
                                     strength=5.0, evidence=[DriverEvidence(key="홍수 위험", detail="영향범위 포함", proximity="읍면동")])],
        coverage=[DomainCoverage(domain="인구", available=True, detail="1개 지표")],
        base_date="2026-07-09",
    )
    base.update(over)
    return BoardResult(**base)


def test_render_full_html_document() -> None:
    html = render_board_html(_board().model_dump())
    assert html.startswith("<!doctype html>") and html.rstrip().endswith("</html>")
    for must in ("<title>", "설계 드라이버", "방재·침수 대비", "여의도동", "전국 대비", "45.1%"):
        assert must in html
    # 지수 113 = 45.1/36.1×100 이 지수 막대로
    assert "125" in html  # index


def test_render_escapes_html() -> None:
    b = _board(use_type="<script>alert(1)</script>")
    html = render_board_html(b.model_dump())
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_render_with_synthesis_and_map() -> None:
    b = _board(synthesis=Synthesis(
        interpretation="사실 서술", interpretation_source="ai", interpretation_model="claude-sonnet-5",
        judgment="AI 의견", judgment_source="ai", judgment_model="claude-opus-4-8",
        judgment_label="검증 보장 없음"))
    html = render_board_html(b.model_dump(), satellite_data_uri="data:image/jpeg;base64,AAAA")
    assert "① 사실 종합" in html and "② AI 판단" in html
    assert 'src="data:image/jpeg;base64,AAAA"' in html  # 지도 앵커 임베드


def test_board_view_endpoint_saves_and_returns_url(monkeypatch) -> None:
    monkeypatch.setattr("app.routers.board.board", lambda req: _board())
    monkeypatch.setattr("app.routers.board._satellite_anchor", lambda *a, **k: None)
    r = client.post("/board/view", json={"address": "서울 영등포구 여의대로 24", "use_type": "주거"})
    assert r.status_code == 200
    body = r.json()
    assert body["url"].startswith("/files/boards/board_") and body["url"].endswith(".html")
    assert body["site"] == "영등포구" and body["has_map"] is False
    # 저장된 파일이 실제로 있고 완결 HTML
    from app.config import OUT_DIR
    fp = OUT_DIR / "boards" / body["url"].split("/")[-1]
    assert fp.exists() and fp.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_board_view_address_error_passthrough(monkeypatch) -> None:
    monkeypatch.setattr("app.routers.board.board",
                        lambda req: JSONResponse(status_code=422, content={"code": "ADDR_UNRESOLVED", "message": "x"}))
    r = client.post("/board/view", json={"address": "없는주소", "use_type": "주거"})
    assert r.status_code == 422 and r.json()["code"] == "ADDR_UNRESOLVED"
