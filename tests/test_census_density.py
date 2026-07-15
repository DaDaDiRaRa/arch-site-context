"""모드A 밀도정규화 (§8.6) 테스트 — census count 를 per-천명 + 동적 전국대비로 (네트워크 없음).

raw count 를 전국 총량과 비교하는 무의미를 해소: 시군구 count/시군구인구 vs 전국 count/전국인구.
census_multidim·fetch_total_pop 를 monkeypatch — 전국 값도 크랙 엔진이 준다는 전제(라이브 검증됨).
"""

from __future__ import annotations

from app.services import census_density


def _patch(monkeypatch, sgg_pop=371362, nat_pop=51720611):
    # 시군구 vs 전국 census count (city_name 으로 구분)
    def _fake_census(org, tbl, itm, city_name, prd, **k):
        if city_name == "전국":
            nat = {"DT_1BD1032": 7538736, "DT_1JU1512": 1599086, "DT_1NW1037": 952026}
            return {"value": nat.get(tbl, 1000000), "year": "2023"}, []
        sgg = {"DT_1BD1032": 96993, "DT_1JU1512": 2292, "DT_1NW1037": 9036}
        return {"value": sgg.get(tbl, 100), "year": "2023"}, []

    def _fake_pop(code, cache=None):
        return nat_pop if code == "00" else sgg_pop

    monkeypatch.setattr(census_density.census_multidim, "fetch_census_indicator", _fake_census)
    monkeypatch.setattr(census_density, "fetch_total_pop", _fake_pop)


def test_density_normalizes_per_capita_with_national(monkeypatch) -> None:
    _patch(monkeypatch)
    facts, _ = census_density.collect_density_facts("11560", "영등포구", "서울", "상업")
    biz = next(f for f in facts if f["item"] == "사업체수(천명당)")
    # 시군구 96993/371362×1000 = 261.2 · 전국 7538736/51720611×1000 = 145.8
    assert biz["value"] == 261.2
    assert biz["national_avg"] == 145.8
    assert biz["unit"] == "개/천명" and biz["scope"] == "영등포구"
    assert biz["scope_level"] == "시군구" and biz["source_tbl"] == "DT_1BD1032"
    # value > national → 지수>100 (Fact 가 자동 유도) — 여기선 재료가 맞는지만
    assert biz["value"] > biz["national_avg"]


def test_density_legal_use_and_profiles(monkeypatch) -> None:
    _patch(monkeypatch)
    # 주거 프로파일 → 빈집·신혼부부
    res = {f["item"] for f in census_density.collect_density_facts("11560", "영등포구", "서울", "주거")[0]}
    assert res == {"빈집(천명당)", "신혼부부(천명당)"}
    # 법적 용도(공동주택→주거)도 동일
    legal = {f["item"] for f in census_density.collect_density_facts("11560", "영등포구", "서울", "공동주택")[0]}
    assert legal == res


def test_density_graceful_when_no_population(monkeypatch) -> None:
    _patch(monkeypatch, sgg_pop=None)
    facts, notes = census_density.collect_density_facts("11560", "영등포구", "서울", "상업")
    assert facts == []
    assert any("분모" in n for n in notes)


def test_density_none_for_unknown_use(monkeypatch) -> None:
    _patch(monkeypatch)
    facts, _ = census_density.collect_density_facts("11560", "영등포구", "서울", "우주정거장")
    assert facts == []  # 프로파일 미해석 → 지표 없음
