"""app/deck/site_glb.py — 건물매싱 GLB(§8.15). 네트워크는 monkeypatch 로 대체."""
from __future__ import annotations

import pygltflib
from fastapi.testclient import TestClient

import app.deck.site_glb as sg
import app.deck.style as k
from app.main import app

client = TestClient(app)


class _FakeSite:
    lat, lon, pnu = 37.521, 126.924, "P1"


def test_ear_clip_triangulates_concave_polygon() -> None:
    l_shape = [(0, 0), (4, 0), (4, 2), (2, 2), (2, 4), (0, 4)]
    tris = sg._ear_clip(l_shape)
    assert len(tris) == len(l_shape) - 2
    area = sum(abs((l_shape[j][0]-l_shape[i][0])*(l_shape[kk][1]-l_shape[i][1])
                   - (l_shape[j][1]-l_shape[i][1])*(l_shape[kk][0]-l_shape[i][0])) / 2
               for i, j, kk in tris)
    assert area == 12.0  # 4x4 정사각 - 2x2 모서리


def test_build_site_glb_round_trips_with_provenance_extras(monkeypatch) -> None:
    monkeypatch.setattr("app.services.site_seed.build_site", lambda addr: _FakeSite())
    ox, oy = k.latlon_to_local(37.521, 126.924, 0.0, 0.0)
    model = {"stats": {"origin_offset": [ox, oy]},
             "geometry": {"buildings": [
                 {"footprint": [[0, 0], [10, 0], [10, 10], [0, 10]], "height": 20.0},
                 {"footprint": [[50, 60], [70, 60], [70, 70], [50, 70]], "height": 45.0},
             ]}}
    monkeypatch.setattr(sg.clients, "fetch_model", lambda *a, **kw: model)

    data = sg.build_site_glb("서울 영등포구 여의대로 24")
    assert data[:4] == b"glTF"
    gltf = pygltflib.GLTF2.load_from_bytes(data)
    assert len(gltf.nodes) == 2
    assert all(n.extras.get("source_ref") == "arch-site-model:geometry.buildings" for n in gltf.nodes)
    heights = sorted(n.extras["height_m"] for n in gltf.nodes)
    assert heights == [20.0, 45.0]
    assert gltf.binary_blob() is not None


def test_build_site_glb_no_model_is_value_error(monkeypatch) -> None:
    monkeypatch.setattr("app.services.site_seed.build_site", lambda addr: _FakeSite())
    monkeypatch.setattr(sg.clients, "fetch_model", lambda *a, **kw: None)
    import pytest
    with pytest.raises(ValueError):
        sg.build_site_glb("서울 영등포구 여의대로 24")


def test_deck_glb_endpoint_streams_glb(monkeypatch) -> None:
    monkeypatch.setattr("app.deck.site_glb.build_site_glb", lambda *a, **kw: b"glTFDATA")
    r = client.post("/deck/glb", json={"address": "서울 영등포구 여의대로 24"})
    assert r.status_code == 200
    assert r.content == b"glTFDATA"
    assert r.headers.get("content-type") == "model/gltf-binary"


def test_deck_glb_addr_error(monkeypatch) -> None:
    def boom(*a, **kw):
        raise ValueError("주소 해석 실패")
    monkeypatch.setattr("app.deck.site_glb.build_site_glb", boom)
    r = client.post("/deck/glb", json={"address": "x"})
    assert r.status_code == 422
    assert "주소" in r.json()["detail"]


def test_build_site_glb_missing_origin_offset_is_value_error(monkeypatch) -> None:
    """stats.origin_offset 없으면 KeyError(→500) 가 아니라 하드블록(→422 사유 표시).

    '건물 모델 없음' 과 같은 계열의 실패다 — 좌표원점 없이는 대지-원점 재투영을 할 수 없다.
    """
    import pytest

    monkeypatch.setattr("app.services.site_seed.build_site", lambda addr: _FakeSite())
    for bad in ({}, {"stats": {}}, {"stats": {"origin_offset": []}}, {"stats": {"origin_offset": [1.0]}}):
        monkeypatch.setattr(sg.clients, "fetch_model", lambda *a, _m=bad, **kw: dict(_m, geometry={"buildings": []}))
        with pytest.raises(ValueError, match="좌표원점"):
            sg.build_site_glb("서울 영등포구 여의대로 24")


def test_deck_glb_missing_origin_offset_returns_422(monkeypatch) -> None:
    """라우터까지 — 500 이 아니라 사유가 담긴 422."""
    monkeypatch.setattr("app.services.site_seed.build_site", lambda addr: _FakeSite())
    monkeypatch.setattr(sg.clients, "fetch_model", lambda *a, **kw: {"stats": {}, "geometry": {"buildings": []}})
    r = client.post("/deck/glb", json={"address": "서울 영등포구 여의대로 24"})
    assert r.status_code == 422
    assert "좌표원점" in r.json()["detail"]
