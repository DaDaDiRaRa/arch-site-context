"""터읽기 MCP 서버 테스트 (T 시리즈 3단계, 네트워크 불필요).

MCP 도구는 기존 서비스를 얇게 래핑할 뿐이므로, 래핑 로직(성공→JSON, 에러응답→error JSON)만
monkeypatch 로 결정적 검증한다. 서비스 자체는 board/diagnose 테스트가 커버.
"""

from __future__ import annotations

import json

from fastapi.responses import JSONResponse

from mcp_server import server


def test_server_registers_two_tools() -> None:
    import asyncio
    tools = {t.name for t in asyncio.new_event_loop().run_until_complete(server.mcp.list_tools())}
    assert {"read_site_context", "diagnose_supply"} <= tools


def test_read_site_context_success(monkeypatch) -> None:
    # board(brief=True) 는 dict 를 반환 → 도구가 그대로 JSON 직렬화
    brief = {"schema_version": "board_brief/1.0", "site": {"sigungu": "영등포구"},
             "design_drivers": [{"rank": 1, "name": "방재·침수 대비"}]}
    monkeypatch.setattr("app.routers.board.board", lambda req: brief)
    out = json.loads(server.read_site_context("서울 영등포구 여의대로 24"))
    assert out["schema_version"] == "board_brief/1.0"
    assert out["design_drivers"][0]["name"] == "방재·침수 대비"


def test_read_site_context_error_maps_to_error_json(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routers.board.board",
        lambda req: JSONResponse(status_code=422, content={"code": "ADDR_UNRESOLVED", "message": "주소 해석 불가"}),
    )
    out = json.loads(server.read_site_context("없는주소"))
    assert out["error"] == "ADDR_UNRESOLVED"
    assert "주소 해석 불가" in out["message"]


def test_diagnose_supply_addr_error(monkeypatch) -> None:
    from app.services.kakao import KakaoError

    def _boom(*a, **k):
        raise KakaoError("no result")
    monkeypatch.setattr("app.services.diagnose.build_diagnosis", _boom)
    out = json.loads(server.diagnose_supply("없는주소"))
    assert out["error"] == "ADDR_UNRESOLVED"
