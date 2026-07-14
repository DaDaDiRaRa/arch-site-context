"""C7 주변현황도 테스트 — 네트워크 monkeypatch (CLAUDE.md §8.13)."""

import httpx

from app.services import surroundings as sr
from app.services import kakao


def _docs(*names):
    # 대상 좌표 근처(반경 내)로 배치
    return [{"name": n, "lat": 37.5 + i * 0.001, "lon": 127.0, "addr": f"{n}로"}
            for i, n in enumerate(names)]


def test_collect_and_narrative(monkeypatch):
    monkeypatch.setattr(kakao, "resolve_coord", lambda a, client=None: {"lat": 37.5, "lon": 127.0})

    def fake_kw(kw, lat, lon, radius, client=None, category_group_code=None):
        table = {
            "지하철역": _docs("노들역 9호선", "노량진역 1호선"),
            "초등학교": _docs("영본초등학교"),
            "중학교": _docs("동양중학교"),
            "공원": _docs("사육신공원", "노들나루공원"),
            "아파트": _docs("삼성래미안", "신동아아파트", "트윈파크"),
            "주민센터": _docs("본동주민센터"),
        }
        return table.get(kw, [])
    monkeypatch.setattr(kakao, "search_keyword", fake_kw)

    r = sr.collect_surroundings("서울 동작구 본동 441", radius=1000, client=httpx.Client())
    by = {c.name: c for c in r.categories}

    assert by["교통"].count == 2
    assert by["교육"].count == 2          # 초 + 중
    assert by["여가"].count == 2
    assert by["주거"].count == 3
    assert by["관공서"].count == 1
    # 색·반경밴드
    assert by["교통"].color == (233, 30, 99)
    assert r.ring_radii == [250, 500, 750]
    # 서술문: 룰 조립 — 역·공원·학교·관공서 언급
    assert "노들역" in r.narrative and "공원" in r.narrative
    assert "1000m 내" in r.narrative


def test_radius_filter_and_cap(monkeypatch):
    monkeypatch.setattr(kakao, "resolve_coord", lambda a, client=None: {"lat": 37.5, "lon": 127.0})

    def fake_kw(kw, lat, lon, radius, client=None, category_group_code=None):
        if kw == "아파트":
            near = [{"name": f"근처{i}", "lat": 37.5 + i * 0.0001, "lon": 127.0, "addr": ""}
                    for i in range(30)]  # 0.0001°≈11m → 30개 모두 반경 1km 내
            far = [{"name": "먼단지", "lat": 37.8, "lon": 127.5, "addr": ""}]  # 반경 밖
            return near + far
        return []
    monkeypatch.setattr(kakao, "search_keyword", fake_kw)
    monkeypatch.setattr(sr, "load_config", lambda: {
        "max_per_category": 5,
        "categories": [{"name": "주거", "keywords": ["아파트"], "color": [1, 2, 3], "narr": "주거단지"}]})

    r = sr.collect_surroundings("a", radius=1000, client=httpx.Client())
    res = r.categories[0]
    assert res.count == 30           # 반경 밖 1건 제외, 반경 내 30건 집계
    assert len(res.items) == 5       # 표시는 cap 5
    assert any("건만" in n for n in res.notes)
