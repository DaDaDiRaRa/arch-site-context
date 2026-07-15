"""B2 — /site 유닛 테스트 (네트워크 불필요, monkeypatch).

키 없는 CI 에서도 실거래·공시지가·건축물대장·재해위험 조립 + **부분 실패 격리**를 잡는다.
molit·vworld·sgis 를 가짜로 대체하고 site_info 오케스트레이션을 검증한다 (절대 원칙 1·3).
"""

from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _loc():
    return SimpleNamespace(
        notes=[], address="서울 영등포구 여의대로 24",
        sgg_code="11560", sigungu="영등포구", sido="서울",
        eupmyeondong="여의동", lat=37.52, lon=126.92,
    )


def _trades(kind, sgg, months, rows):
    return ([{"category": kind, "deal_type": "매매", "area_sqm": 84.9,
              "price_10k": 120000, "deal_ym": "202606"}], [])


def _land_price(lon, lat, **k):
    return ({"price_per_sqm": 29793000, "year": 2025, "pnu": "1156011000",
             "addr": "여의도동 28-1", "jibun": "28-1"}, [])


def _building(pnu, **k):
    return ({"name": "에프케이아이타워", "floors_above": 50, "bcr": 52.75, "far": 940.36}, [])


def _hazards(lat, lon, **k):
    return {"dong_name": "여의도동", "flood": {"in_zone": True, "exposure_scope": "읍면동"},
            "landslide": {"in_zone": False, "exposure_scope": "시군구"},
            "base_year": "2024", "notes": ["홍수 영향범위 포함"]}


def _heatwave(sido, sigungu, **k):
    return {"alert_count": 11, "warning_count": 31, "scope": "서울 권역",
            "base_period": "2024~2025", "notes": []}


def _patch(monkeypatch, **over):
    monkeypatch.setattr("app.routers.site.resolve_address", lambda *a, **k: _loc())
    monkeypatch.setattr("app.routers.site.molit.DEFAULT_TRADE_KINDS", ["토지매매", "아파트매매"])
    monkeypatch.setattr("app.routers.site.molit.fetch_trades", over.get("trades", _trades))
    monkeypatch.setattr("app.routers.site.molit.fetch_building", over.get("building", _building))
    monkeypatch.setattr("app.routers.site.vworld.fetch_land_price", over.get("land", _land_price))
    monkeypatch.setattr("app.routers.site.sgis.fetch_site_hazards", over.get("hazards", _hazards))
    monkeypatch.setattr("app.routers.site.sgis.fetch_heatwave_history", over.get("heatwave", _heatwave))


# ── 정상 조립 ────────────────────────────────────────────────────────────────
def test_site_assembles(monkeypatch) -> None:
    _patch(monkeypatch)
    r = client.post("/site", json={"address": "서울 영등포구 여의대로 24"})
    assert r.status_code == 200
    b = r.json()
    assert b["center"]["sigungu"] == "영등포구"
    assert b["land_price"]["price_per_sqm"] == 29793000
    assert b["building"]["name"] == "에프케이아이타워"
    assert b["hazards"]["flood"]["in_zone"] is True
    assert b["hazards"]["heatwave"]["alert_count"] == 11
    # 실거래 4종(→2종 mock) × 1건씩
    assert len(b["real_estate"]["transactions"]) == 2


# ── 부분 실패 격리: 공시지가·건축물대장 블록 예외 → /site 는 200, 나머지 유지 ──
def test_site_isolates_land_failure(monkeypatch) -> None:
    def _boom(*a, **k):
        raise RuntimeError("VWorld 500")
    _patch(monkeypatch, land=_boom)
    r = client.post("/site", json={"address": "x"})
    assert r.status_code == 200
    b = r.json()
    # 공시지가·건축물대장은 빈값, 재해·실거래는 그대로
    assert b["land_price"]["price_per_sqm"] is None
    assert b["hazards"]["flood"]["in_zone"] is True
    assert len(b["real_estate"]["transactions"]) == 2
    assert any("공시지가" in n for n in b["notes"])


# ── 재해위험 미확보 → graceful (기본 SiteHazards, notes 정직) ────────────────
def test_site_hazards_missing_graceful(monkeypatch) -> None:
    _patch(monkeypatch, hazards=lambda *a, **k: None)
    b = client.post("/site", json={"address": "x"}).json()
    assert b["hazards"]["flood"]["in_zone"] is not True  # 미확인(None) — 추정 안 함
    assert any("재해위험" in n for n in b["notes"])


# ── 주소 해석 실패 = 하드블록 ────────────────────────────────────────────────
def test_site_bad_address_blocks(monkeypatch) -> None:
    from app.services.kakao import KakaoError
    monkeypatch.setattr("app.routers.site.resolve_address",
                        lambda *a, **k: (_ for _ in ()).throw(KakaoError("no result")))
    r = client.post("/site", json={"address": "없는주소"})
    assert r.status_code == 422
    assert r.json()["code"] == "ADDR_UNRESOLVED"
