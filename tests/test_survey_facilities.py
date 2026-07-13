"""조사범위 시설 현황 조사 테스트 — 네트워크 monkeypatch (CLAUDE.md §8.13)."""

import httpx

from app.services import survey_facilities as sf
from app.services import kakao, vworld, childcare


def test_collect_categories_dedup_radius(monkeypatch):
    C = (37.5, 127.0)

    def fake_kw(kw, lat, lon, radius, client=None):
        if kw in ("작은도서관", "도서관"):
            return [
                {"name": "가 도서관", "lat": 37.501, "lon": 127.001, "addr": "가로 1"},
                {"name": "가 도서관", "lat": 37.501, "lon": 127.001, "addr": "가로 1"},  # 중복
                {"name": "먼 도서관", "lat": 37.7, "lon": 127.3, "addr": "먼로 9"},       # 반경 밖
            ]
        if kw == "경로당":
            return [{"name": "나 경로당", "lat": 37.5005, "lon": 127.0, "addr": "나로 2"}]
        if kw == "어린이집":
            return [{"name": "다 어린이집", "lat": 37.4995, "lon": 127.0, "addr": "다로 3"}]
        return []
    monkeypatch.setattr(kakao, "search_keyword", fake_kw)
    monkeypatch.setattr(vworld, "search_vworld",
                        lambda lat, lon, r, kinds, client=None:
                        ([{"name": "라 경로당", "lat": 37.5006, "lon": 127.0006, "kind": "경로당"}], []))
    monkeypatch.setattr(childcare, "fetch_childcare",
                        lambda sgg, region_name="", client=None:
                        ({"count": 50, "total_capacity": 2974, "scope": "동작구"}, []))

    cats = sf.collect_survey_facilities(C[0], C[1], 1000, "11590", "본동", client=httpx.Client())
    by = {c.category: c for c in cats}

    # 도서관: 중복 1건 제거 + 반경 밖 1건 제외 → 1개
    assert by["작은도서관"].count == 1
    assert by["작은도서관"].items[0].addr == "가로 1"
    # 경로당: 카카오 1 + VWorld 1 = 2 (거리순)
    assert by["경로당"].count == 2
    assert any(i.src == "vworld" for i in by["경로당"].items)
    # 어린이집: 목록 1 + 시군구 정원(참고)
    assert by["어린이집"].count == 1
    assert by["어린이집"].capacity == 2974 and by["어린이집"].capacity_scope == "동작구"
    # 면적 미제공 note 항상
    assert any("면적" in n for n in by["작은도서관"].notes)


def test_category_graceful_on_error(monkeypatch):
    def boom(kw, lat, lon, radius, client=None):
        raise RuntimeError("kakao down")
    monkeypatch.setattr(kakao, "search_keyword", boom)
    monkeypatch.setattr(vworld, "search_vworld", lambda *a, **k: ([], []))
    monkeypatch.setattr(childcare, "fetch_childcare", lambda *a, **k: (None, ["없음"]))
    cats = sf.collect_survey_facilities(37.5, 127.0, 1000, "11590", client=httpx.Client())
    # 실패해도 카테고리는 반환(count 0 + note), 앱 안 죽음
    assert len(cats) == 3
    assert all(c.count == 0 for c in cats)
