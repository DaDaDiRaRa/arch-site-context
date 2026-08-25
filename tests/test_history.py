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


def test_history_file_hwpx_gets_hwpx_content_type(monkeypatch) -> None:
    """§8.15 HWP 내보내기 — pptx 전용이던 이력 재다운로드가 hwpx 도 올바른 콘텐츠타입으로."""
    import app.services.history as h

    monkeypatch.setattr(h, "read", lambda gid: (b"HWPXDATA", "종합읽기_x.hwpx") if gid == "def" else None)
    r = client.get("/history/def/file")
    assert r.status_code == 200
    assert r.content == b"HWPXDATA"
    assert "haansofthwp" in r.headers.get("content-type", "")
    assert r.headers["content-disposition"].endswith('download.hwpx"')


def test_history_save_and_read_roundtrip_by_extension(tmp_path, monkeypatch) -> None:
    """services.history — pptx 와 hwpx 가 서로 다른 파일로 저장·조회돼 섞이지 않는다 (로컬 백엔드)."""
    import app.services.history as h
    from app.services.cache import MemoryCache

    monkeypatch.setattr(h, "OUT_DIR", tmp_path)
    monkeypatch.delenv("GCS_CACHE_BUCKET", raising=False)
    monkeypatch.setattr(h, "default_cache", MemoryCache())

    pptx_entry = h.save("board", "주소1", {}, "종합읽기_주소1.pptx", b"PPTXBYTES")
    hwpx_entry = h.save("board", "주소1", {}, "종합읽기_주소1.hwpx", b"HWPXBYTES")

    data, fn = h.read(pptx_entry["id"])
    assert (data, fn) == (b"PPTXBYTES", "종합읽기_주소1.pptx")
    data, fn = h.read(hwpx_entry["id"])
    assert (data, fn) == (b"HWPXBYTES", "종합읽기_주소1.hwpx")
    assert (tmp_path / "history" / f"{pptx_entry['id']}.pptx").exists()
    assert (tmp_path / "history" / f"{hwpx_entry['id']}.hwpx").exists()
