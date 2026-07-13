"""C1 조사범위 걸침 합산 엔진 테스트 — 네트워크 monkeypatch (CLAUDE.md §8.13).

합성 지오메트리로 걸침율×인구세대 합산·계(대지 시군구 포함분)·타시군구 ⚠플래그를 검증한다.
shapely 자체가 아니라 우리 집계 로직을 본다.
"""

import httpx

from app.services import survey, kakao, sgis, jumin


def _square(cx, cy, half=100):
    return {"type": "Polygon", "coordinates": [[
        [cx - half, cy - half], [cx + half, cy - half],
        [cx + half, cy + half], [cx - half, cy + half], [cx - half, cy - half]]]}


def test_survey_aggregation(monkeypatch):
    # 대지: UTM 원점, 반경 1000 원. 세 행정동 — A(대지동, 완전포함), B(부분걸침), C(타시군구)
    monkeypatch.setattr(kakao, "resolve_coord", lambda a, client=None: {"lat": 37.5, "lon": 127.0})

    def fake_hdong(lat, lon):
        if abs(lat - 37.5) < 0.01:
            return {"code": "1111000000", "name": "대지동"}       # 대지 → 시군구 11110
        if abs(lon - 0) < 50:
            return {"code": "1111000000", "name": "대지동"}       # A 중심 x≈0
        if abs(lon - 1050) < 120:
            return {"code": "1111000001", "name": "비동"}         # B 중심 x≈1050 (같은 시군구)
        if abs(lon + 500) < 120:
            return {"code": "2222000000", "name": "타동"}         # C 중심 x≈-500 (타 시군구)
        return None
    monkeypatch.setattr(kakao, "coord_to_hdong", fake_hdong)

    monkeypatch.setattr(sgis, "get_token", lambda client, cache=None: "TOK")
    monkeypatch.setattr(sgis, "to_utmk", lambda lat, lon, tok, client: (0.0, 0.0))

    def fake_get(client, path, params, timeout=20.0):
        if "boundary/userarea" in path:
            return {"features": [
                {"geometry": _square(0, 0), "properties": {"adm_nm": "서울 대지구 대지동"}},
                {"geometry": _square(1050, 0), "properties": {"adm_nm": "서울 대지구 비동"}},
                {"geometry": _square(-500, 0), "properties": {"adm_nm": "타시 타구 타동"}},
            ]}
        if "transcoord" in path:  # posX(=centroid.x) 를 lon 으로 echo
            return {"result": {"posX": params["posX"], "posY": params["posY"]}}
        return {}
    monkeypatch.setattr(sgis, "_get", fake_get)

    def fake_jumin(sgg, ym=None, cache=None, client=None):
        if sgg == "11110":
            return {"ym": "202604", "dongs": {
                "1111000000": {"name": "대지동", "population": 10000, "households": 5000},
                "1111000001": {"name": "비동", "population": 8000, "households": 4000}}}, []
        if sgg == "22220":
            return {"ym": "202604", "dongs": {
                "2222000000": {"name": "타동", "population": 6000, "households": 3000}}}, []
        return None, ["없음"]
    monkeypatch.setattr(jumin, "fetch_dong_stats", fake_jumin)

    r = survey.survey_area("서울 대지구 대지동 1", radius=1000, client=httpx.Client())

    assert r.site_sgg == "11110"
    assert r.ym == "202604"
    by = {d.name: d for d in r.dongs}
    assert set(by) == {"대지동", "비동", "타동"}

    # A: 완전 포함 → 걸침율 1.0, 적용=총량
    a = by["대지동"]
    assert abs(a.ratio - 1.0) < 0.001
    assert a.applied_pop == 10000 and a.applied_hh == 5000
    assert a.same_sgg is True and a.flagged is False

    # B: 부분 걸침 → 적용 = round(총량 × 걸침율) 자기일관
    b = by["비동"]
    assert 0 < b.ratio < 1
    assert b.applied_hh == round(4000 * b.ratio)
    assert b.applied_pop == round(8000 * b.ratio)
    assert b.same_sgg is True

    # C: 타 시군구 → ⚠플래그, 계에서 제외
    c = by["타동"]
    assert c.same_sgg is False and c.flagged is True

    # 계 = A + B (대지 시군구 포함분만), C 제외
    assert r.applied_hh_total == 5000 + round(4000 * b.ratio)
    assert r.applied_pop_total == 10000 + round(8000 * b.ratio)


def test_survey_site_resolve_fail(monkeypatch):
    monkeypatch.setattr(kakao, "resolve_coord", lambda a, client=None: {"lat": 0.0, "lon": 0.0})
    monkeypatch.setattr(kakao, "coord_to_hdong", lambda lat, lon: None)
    r = survey.survey_area("없는주소", client=httpx.Client())
    assert r.dongs == [] and any("해석 실패" in n for n in r.notes)
