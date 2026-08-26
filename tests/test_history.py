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


def test_history_file_uses_saved_extension_for_all_formats(monkeypatch) -> None:
    """§8.15 — zip(SVG)·dxf·glb 도 저장된 확장자·콘텐츠타입 그대로 내려간다.

    라우터가 확장자 표를 따로 들고 있어(pptx/hwpx 2종만) zip 이 `download.pptx` 로 나가던 것.
    이제 services.history.content_type 하나만 본다.
    """
    import app.services.history as h

    cases = [
        ("대지분석지도_x.zip", ".zip", "application/zip"),
        ("대지계획도_x.dxf", ".dxf", "application/dxf"),
        ("건물매싱_x.glb", ".glb", "model/gltf-binary"),
    ]
    for fn, ext, media in cases:
        monkeypatch.setattr(h, "read", lambda gid, _f=fn: (b"BLOB", _f))
        r = client.get("/history/any/file")
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith(media), fn
        assert r.headers["content-disposition"].endswith(f'download{ext}"'), fn


def test_content_type_falls_back_for_unknown_extension() -> None:
    """모르는 확장자는 pptx 로 가정(저장 때 _ext_of 와 같은 규칙) — 표가 한 곳뿐이라 항상 일치."""
    import app.services.history as h

    assert h.content_type("x.zip") == (".zip", "application/zip")
    assert h.content_type("x.unknown")[0] == h._ext_of("x.unknown")
