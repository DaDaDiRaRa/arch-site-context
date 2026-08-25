"""app/deck/site_dxf.py — 통합 CAD 대지계획도(§8.15). 네트워크는 monkeypatch 로 대체."""
from __future__ import annotations

import ezdxf
import io as _io

from fastapi.testclient import TestClient

import app.deck.site_dxf as sd
import app.deck.style as k
from app.main import app

client = TestClient(app)


class _FakeSite:
    lat, lon, pnu = 37.521, 126.924, "P1"


def _patch_common(monkeypatch, model=None):
    monkeypatch.setattr("app.services.site_seed.build_site", lambda addr: _FakeSite())
    monkeypatch.setattr(sd.clients, "fetch_model", lambda *a, **kw: model)
    monkeypatch.setattr(sd.clients, "fetch_law", lambda *a, **kw: {"zone_use": "일반상업지역", "pnu": "P1",
                                                                     "parcel_geometry": None})
    monkeypatch.setattr(sd.clients, "fetch_facilities", lambda *a, **kw: {"results": []})


def test_build_site_dxf_without_model_has_site_and_radius(monkeypatch) -> None:
    _patch_common(monkeypatch, model=None)
    data = sd.build_site_dxf("서울 영등포구 여의대로 24", "주거", 1000)
    doc = ezdxf.read(_io.StringIO(data.decode("utf-8")))
    msp = doc.modelspace()
    layers = {l.dxf.name for l in doc.layers}
    assert {"SITE", "REF-RADIUS", "ANNOTATION"} <= layers
    circles = list(msp.query("CIRCLE"))
    assert len(circles) == len(sd._REF_RADII) + 1  # 참조원 3 + SITE 원점 원


def test_build_site_dxf_with_model_places_building_near_origin(monkeypatch) -> None:
    ox, oy = k.latlon_to_local(37.521, 126.924, 0.0, 0.0)
    model = {"stats": {"origin_offset": [ox, oy]},
             "geometry": {"buildings": [{"footprint": [[0, 0], [10, 0], [10, 10], [0, 10]], "height": 20.0}]}}
    _patch_common(monkeypatch, model=model)
    data = sd.build_site_dxf("서울 영등포구 여의대로 24", "주거", 1000)
    doc = ezdxf.read(_io.StringIO(data.decode("utf-8")))
    msp = doc.modelspace()
    polys = [e for e in msp.query("LWPOLYLINE") if e.dxf.layer.startswith("BLDG-")]
    assert len(polys) == 1
    pts = list(polys[0].get_points("xy"))
    # 대지가 원점이므로 건물 footprint(모델 원점 부근)도 원점 근방(수백m 이내)에 있어야 함
    assert all(abs(x) < 500 and abs(y) < 500 for x, y in pts)


def test_deck_dxf_endpoint_streams_dxf(monkeypatch) -> None:
    monkeypatch.setattr("app.deck.site_dxf.build_site_dxf", lambda *a, **kw: b"DXFDATA")
    r = client.post("/deck/dxf", json={"address": "서울 영등포구 여의대로 24"})
    assert r.status_code == 200
    assert r.content == b"DXFDATA"
    assert r.headers.get("content-type") == "application/dxf"


def test_deck_dxf_addr_error(monkeypatch) -> None:
    def boom(*a, **kw):
        raise ValueError("주소 해석 실패")
    monkeypatch.setattr("app.deck.site_dxf.build_site_dxf", boom)
    r = client.post("/deck/dxf", json={"address": "x"})
    assert r.status_code == 422
    assert "주소" in r.json()["detail"]
