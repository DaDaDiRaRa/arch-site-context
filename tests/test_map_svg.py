"""app/deck/map_svg.py — 지도 4종 독립 SVG 출력 (§8.15).

네트워크 호출은 monkeypatch 로 대체. 저수준 빌더가 유효한 SVG XML을 만드는지,
데이터에 묶인 도형마다 id·data-source-ref(근거) 가 붙는지를 검증한다.
"""
from __future__ import annotations

import io

from lxml import etree
from PIL import Image
from fastapi.testclient import TestClient

import app.deck.map_svg as msvg
import app.deck.style as k
from app.main import app

client = TestClient(app)

FAKE_META = {"zoom": 17, "cx": 1000.0, "cy": 1000.0, "radius_px": 500.0}


def _make_fake_png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (100, 120, 140)).save(buf, format="PNG")
    return buf.getvalue()


FAKE_PNG = _make_fake_png()


def _fake_basemap(*a, **kw):
    return FAKE_META, FAKE_PNG


def test_svg_wide_has_station_and_radius_provenance(monkeypatch) -> None:
    fac = {"results": [{"name": "여의도역 5호선", "kind": "지하철역", "lat": 37.521, "lon": 126.924}]}
    monkeypatch.setattr(msvg.clients, "fetch_facilities", lambda *a, **kw: fac)
    monkeypatch.setattr(msvg.clients, "fetch_basemap", _fake_basemap)
    monkeypatch.setattr(k, "to_canvas", lambda lat, lon, z, mcx, mcy, size: (size / 2, size / 2))

    svg = msvg.svg_wide("서울 영등포구 여의대로 24", 37.521, 126.924, {"zone_use": "일반상업지역", "pnu": "P1"},
                        {"land_price": {"price_per_sqm": 1000000, "year": 2025, "jibun": "1-1"}})
    assert svg is not None
    root = etree.fromstring(svg.encode("utf-8"))
    assert root.tag.endswith("}svg")
    assert 'id="radius-500"' in svg and 'id="radius-2000"' in svg
    assert 'data-source-ref="computed:basemap-scale"' in svg
    assert "kakao:facilities.results[name=여의도역]" in svg
    assert "law:zone_use" in svg  # 정보패널 근거 라벨
    assert 'href="data:image/jpeg;base64,' in svg  # 위성이미지는 JPEG로 재인코딩(용량 절감)
    assert svg.count("base64,") == 1  # href 중복 임베드 없음(예전엔 xlink:href로 2배였음)


def test_svg_use_renders_building_polygon_with_provenance(monkeypatch) -> None:
    monkeypatch.setattr(msvg.clients, "fetch_facilities", lambda *a, **kw: {"results": []})
    monkeypatch.setattr(msvg.clients, "fetch_basemap", _fake_basemap)
    monkeypatch.setattr(k, "local_to_latlon", lambda lx, ly, ox, oy: (lx, ly))
    monkeypatch.setattr(k, "to_canvas", lambda lat, lon, z, mcx, mcy, size: (lat, lon))

    model = {
        "stats": {"origin_offset": [0.0, 0.0]},
        "geometry": {"buildings": [
            {"footprint": [[100, 100], [200, 100], [200, 200], [100, 200]], "height": 45.0},
        ]},
    }
    svg = msvg.svg_use("서울 영등포구 여의대로 24", 37.521, 126.924, model, parcel=None)
    assert svg is not None
    root = etree.fromstring(svg.encode("utf-8"))
    polys = root.findall(f".//{{{msvg.NS}}}polygon[@id='bldg-0']")
    assert len(polys) == 1
    assert polys[0].get("data-source-ref") == "arch-site-model:geometry.buildings"
    assert 'id="site"' in svg  # parcel 없을 때도 SITE 표기(알약)는 항상 그려짐


def test_deck_svg_streams_zip(monkeypatch) -> None:
    def fake_build(address):
        return {"wide": "<svg xmlns='http://www.w3.org/2000/svg'/>", "use": "<svg xmlns='http://www.w3.org/2000/svg'/>"}

    monkeypatch.setattr("app.deck.map_svg.build_map_svgs", fake_build)
    r = client.post("/deck/svg", json={"address": "서울 영등포구 여의대로 24", "use_type": "주거"})
    assert r.status_code == 200
    assert r.headers.get("content-type") == "application/zip"

    import io
    import zipfile
    names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    assert "광역입지도.svg" in names
    assert "건물용도현황.svg" in names


def test_deck_svg_addr_error(monkeypatch) -> None:
    def boom(*a, **kw):
        raise ValueError("주소 해석 실패")

    monkeypatch.setattr("app.deck.map_svg.build_map_svgs", boom)
    r = client.post("/deck/svg", json={"address": "x"})
    assert r.status_code == 422
    assert "주소" in r.json()["detail"]


def test_deck_svg_empty_result_is_422(monkeypatch) -> None:
    monkeypatch.setattr("app.deck.map_svg.build_map_svgs", lambda *a, **kw: {})
    r = client.post("/deck/svg", json={"address": "서울 영등포구 여의대로 24"})
    assert r.status_code == 422
