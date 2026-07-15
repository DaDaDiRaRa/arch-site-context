"""GET /history · /history/{id}/file — 생성물 이력 (재다운로드)."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_history_list(monkeypatch) -> None:
    import app.services.history as h

    monkeypatch.setattr(h, "list_entries", lambda: [{
        "id": "abc", "kind": "deck", "title": "서울 영등포구 여의대로 24",
        "params": {"use_type": "주거", "radius": 1000}, "created": "2026-07-15T22:00:00",
        "size": 19_000_000, "backend": "local", "filename": "대지분석_x.pptx",
    }])
    r = client.get("/history")
    assert r.status_code == 200
    items = r.json()["items"]
    assert items and items[0]["id"] == "abc" and items[0]["kind"] == "deck"


def test_history_file(monkeypatch) -> None:
    import app.services.history as h

    monkeypatch.setattr(h, "read", lambda gid: (b"PPTXDATA", "a.pptx") if gid == "abc" else None)
    r = client.get("/history/abc/file")
    assert r.status_code == 200
    assert r.content == b"PPTXDATA"
    assert "presentationml" in r.headers.get("content-type", "")
    assert client.get("/history/nope/file").status_code == 404
