"""모드 A 반경 모드 단위테스트 (D2 → /analyze). 네트워크 없음 (SGIS monkeypatch).

반경 모드: 인구/연령 facts 를 SGIS 집계구 합산으로 교체 + 인구밀도·평균나이 신규,
인구 외 지표(가구·대기질)는 시군구 유지 (절대 원칙 4). SGIS 실패 시 graceful 폴백.
"""

from __future__ import annotations

from app.routers import analyze as analyze_router


class _Loc:
    lat, lon = 37.52, 126.92


def _base_facts():
    return [
        {"item": "고령인구비율", "value": 19.2, "national_avg": 21.2, "unit": "%",
         "source_tbl": "DT_1B04005N", "year": 2025, "scope": "영등포구", "scope_level": "시군구"},
        {"item": "총인구수", "value": 371362, "national_avg": 51117378, "unit": "명",
         "source_tbl": "DT_1B04005N", "year": 2025, "scope": "영등포구", "scope_level": "시군구"},
        {"item": "1인가구비율", "value": 45.1, "national_avg": 36.1, "unit": "%",
         "source_tbl": "DT_1JC1511", "year": 2024, "scope": "영등포구", "scope_level": "시군구"},
    ]


_RP = {
    "radius": 1000, "total_pop": 29281, "tong_count": 62, "tong_matched": 60,
    "youth_share": 5.6, "aged_share": 16.1, "working_share": 78.2, "avg_age": 42.5,
    "density_per_km2": 9320, "base_year": "2023", "source": "sgis",
    "notes": ["집계구 2개 미매칭 — 합산 제외."],
}


def test_apply_radius_overrides_and_adds(monkeypatch) -> None:
    monkeypatch.setattr("app.services.sgis.fetch_radius_population", lambda *a, **k: _RP)
    facts, notes = _base_facts(), []
    ok = analyze_router._apply_radius(facts, notes, _Loc(), 1000)
    assert ok is True
    by = {f["item"]: f for f in facts}
    # 인구/연령 → SGIS 반경값 + scope, national_avg 유지
    assert by["고령인구비율"]["value"] == 16.1
    assert by["고령인구비율"]["scope_level"] == "반경" and by["고령인구비율"]["scope"] == "반경 1000m"
    assert by["고령인구비율"]["national_avg"] == 21.2
    assert by["총인구수"]["value"] == 29281
    # 1인가구 → SGIS 미제공, 시군구 유지
    assert by["1인가구비율"]["value"] == 45.1 and by["1인가구비율"]["scope_level"] == "시군구"
    # 신규 지표
    assert by["인구밀도"]["value"] == 9320 and by["인구밀도"]["scope_level"] == "반경"
    assert by["평균나이"]["value"] == 42.5
    assert any("미매칭" in n for n in notes)


def test_apply_radius_graceful_when_none(monkeypatch) -> None:
    monkeypatch.setattr("app.services.sgis.fetch_radius_population", lambda *a, **k: None)
    facts, notes = _base_facts(), []
    ok = analyze_router._apply_radius(facts, notes, _Loc(), 1000)
    assert ok is False
    # 원본 유지, 폴백 note
    assert {f["item"]: f for f in facts}["고령인구비율"]["value"] == 19.2
    assert any("폴백" in n for n in notes)
