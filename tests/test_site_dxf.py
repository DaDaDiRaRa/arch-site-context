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
    assert len(circles) == len(sd._ref_radii(1000)) + 1  # 참조원 3 + SITE 원점 원


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


# ── 도면 반경(plan_radius) — `/deck/full` 의 데이터 반경과 분리된 축 (§8.15 배치2) ──

def test_ref_radii_follow_plan_radius() -> None:
    """참조원은 도면 반경에서 파생된다 — 예전엔 (100,200,350) 고정이라 반경과 어긋났다."""
    from app.deck.site_dxf import _ref_radii

    assert _ref_radii(350)[-1] == 350
    assert _ref_radii(1000) == (300, 750, 1000)
    assert _ref_radii(200) == (50, 150, 200)
    for r in (50, 100, 350, 500, 1000, 2000):
        rr = _ref_radii(r)
        assert rr[-1] == r and len(rr) == len(set(rr)) and list(rr) == sorted(rr)


def test_plan_radius_drives_model_fetch(monkeypatch) -> None:
    """요청한 도면 반경이 arch-site-model 요청 반경으로 그대로 간다(받은 값을 실제로 쓴다)."""
    seen = {}
    monkeypatch.setattr("app.services.site_seed.build_site", lambda addr: _FakeSite())
    monkeypatch.setattr(sd.clients, "fetch_model",
                        lambda addr, r: seen.setdefault("model_radius", r) and None)
    monkeypatch.setattr(sd.clients, "fetch_law", lambda *a, **kw: None)
    monkeypatch.setattr(sd.clients, "fetch_facilities", lambda *a, **kw: None)

    sd.build_site_dxf("서울 영등포구 여의대로 24", "주거", 800)
    assert seen["model_radius"] == 800


def test_deck_dxf_defaults_and_rejects_over_limit(monkeypatch) -> None:
    """미지정이면 기본 350m. 형제앱 계약(2000m) 초과는 조용히 clamp 하지 않고 422."""
    seen = {}

    def fake(address, use_type, model_radius_m):
        seen["r"] = model_radius_m
        return b"DXF"

    monkeypatch.setattr("app.deck.site_dxf.build_site_dxf", fake)
    assert client.post("/deck/dxf", json={"address": "서울 영등포구 여의대로 24"}).status_code == 200
    assert seen["r"] == 350

    client.post("/deck/dxf", json={"address": "서울 영등포구 여의대로 24", "plan_radius": 1200})
    assert seen["r"] == 1200

    r = client.post("/deck/dxf", json={"address": "서울 영등포구 여의대로 24", "plan_radius": 5000})
    assert r.status_code == 422  # ge/le 검증 — 조용한 clamp 없음 (절대 원칙 3)
