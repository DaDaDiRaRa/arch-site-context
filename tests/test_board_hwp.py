"""POST /board/hwp — 종합읽기 HWP(HWPX) 보고서 (§8.15, /board/pptx 옆의 문서형 옵션).

board()·kordoc_client 는 무겁거나(외부 API) 로컬 전용 도구(kordoc)라 monkeypatch —
라우터 배선·graceful 미설치 응답만 검증한다.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class _FakeBoard:
    def __init__(self, data=None):
        self._data = data or {"site": {"address": "서울 영등포구 여의대로 24"}}

    def model_dump(self):
        return self._data

    facts = []
    diagnoses = []
    hazards = None
    cross_implications = []
    design_drivers = []
    archetype = None


def test_board_hwp_streams(monkeypatch) -> None:
    import app.routers.board as bmod
    from app.services import kordoc_client as kc

    monkeypatch.setattr(kc, "available", lambda: True)
    monkeypatch.setattr(kc, "markdown_to_hwpx", lambda md, **k: b"HWPXDATA")
    monkeypatch.setattr(bmod, "board", lambda req: _FakeBoard())
    r = client.post("/board/hwp", json={"address": "서울 영등포구 여의대로 24", "use_type": "주거"})
    assert r.status_code == 200
    assert r.content == b"HWPXDATA"
    assert "haansofthwp" in r.headers.get("content-type", "")


def test_board_hwp_unavailable_returns_422(monkeypatch) -> None:
    from app.services import kordoc_client as kc

    monkeypatch.setattr(kc, "available", lambda: False)
    r = client.post("/board/hwp", json={"address": "서울 영등포구 여의대로 24", "use_type": "주거"})
    assert r.status_code == 422
    body = r.json()
    assert body["code"] == "KORDOC_UNAVAILABLE"


def test_board_hwp_conversion_failure_returns_422(monkeypatch) -> None:
    import app.routers.board as bmod
    from app.services import kordoc_client as kc

    def boom(md, **k):
        raise kc.KordocError("변환 실패 테스트")

    monkeypatch.setattr(kc, "available", lambda: True)
    monkeypatch.setattr(kc, "markdown_to_hwpx", boom)
    monkeypatch.setattr(bmod, "board", lambda req: _FakeBoard())
    r = client.post("/board/hwp", json={"address": "서울 영등포구 여의대로 24", "use_type": "주거"})
    assert r.status_code == 422
    assert r.json()["code"] == "KORDOC_FAILED"


def test_board_hwp_propagates_board_error(monkeypatch) -> None:
    """board() 가 하드블록(422)을 내면 그대로 전달 — 추정으로 덮지 않는다."""
    import app.routers.board as bmod
    from fastapi.responses import JSONResponse
    from app.services import kordoc_client as kc

    monkeypatch.setattr(kc, "available", lambda: True)
    monkeypatch.setattr(bmod, "board", lambda req: JSONResponse(status_code=422, content={"code": "NO_DATA"}))
    r = client.post("/board/hwp", json={"address": "x", "use_type": "주거"})
    assert r.status_code == 422
    assert r.json()["code"] == "NO_DATA"
