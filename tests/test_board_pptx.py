"""POST /board/pptx — 종합읽기 A3 PPTX (S4 종합 기본 포함).

board()·build_board_deck 은 무겁고 외부 API 를 태우므로 monkeypatch — 라우터 배선·응답만 검증.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class _FakeBoard:
    def model_dump(self):
        return {"site": {"address": "서울 영등포구 여의대로 24"}}


def test_board_pptx_streams(monkeypatch) -> None:
    import app.deck.board_slides as bs
    import app.routers.board as bmod

    monkeypatch.setattr(bmod, "board", lambda req: _FakeBoard())
    monkeypatch.setattr(bs, "build_board_deck", lambda d: b"PPTXDATA")
    r = client.post("/board/pptx", json={"address": "서울 영등포구 여의대로 24", "use_type": "주거"})
    assert r.status_code == 200
    assert r.content == b"PPTXDATA"
    assert "presentationml" in r.headers.get("content-type", "")
