"""POST /deck/full — 대지분석 덱 라우터 (deck-builder 흡수, 구 별도 서비스).

build_full_deck 은 외부 API 를 태우므로 monkeypatch 로 대체 — 라우터 배선·응답만 검증.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_deck_full_streams_pptx(monkeypatch) -> None:
    import app.deck.map_slides as ms

    monkeypatch.setattr(ms, "build_full_deck", lambda *a, **k: b"PPTXDATA")
    r = client.post("/deck/full", json={"address": "서울 영등포구 여의대로 24", "use_type": "주거"})
    assert r.status_code == 200  # 405/404 아님 — 라우트가 정적마운트보다 먼저 잡힘
    assert r.content == b"PPTXDATA"
    assert "presentationml" in r.headers.get("content-type", "")


def test_deck_full_addr_error(monkeypatch) -> None:
    import app.deck.map_slides as ms

    def boom(*a, **k):
        raise ValueError("주소 해석 실패")

    monkeypatch.setattr(ms, "build_full_deck", boom)
    r = client.post("/deck/full", json={"address": "x"})
    assert r.status_code == 422
    assert "주소" in r.json()["detail"]
