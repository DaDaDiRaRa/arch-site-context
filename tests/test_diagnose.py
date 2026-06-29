"""P11 수급진단 테스트.

순수 cross 로직(레벨 분류·signal·소견)은 네트워크 없이 결정적으로 검증.
전체 흐름은 stats·facilities 를 모킹해 검증. 라이브는 키 있을 때만 (skipif).
부족/과잉은 휴리스틱 — 모든 진단이 '참고' 태그여야 한다 (절대 원칙 5).
"""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

from app.schemas.facility import Center, FacilityResult
from app.services import diagnose

load_dotenv()


# ── 수요/공급 레벨 분류 ──────────────────────────────────────────────────
def test_demand_level_thresholds() -> None:
    # 전국 10, margin 1 → 11 초과 높음, 9 미만 낮음, 그 사이 평이
    assert diagnose._demand_level(12.0, 10.0, 1) == "높음"
    assert diagnose._demand_level(8.0, 10.0, 1) == "낮음"
    assert diagnose._demand_level(10.5, 10.0, 1) == "평이"
    assert diagnose._demand_level(99.0, None, 1) == "불명"  # 비교기준 없음


def test_supply_level_thresholds() -> None:
    # 기본 radius=1000m (scale=1.0)
    assert diagnose._supply_level_count(2, 3, 10) == "적음"
    assert diagnose._supply_level_count(15, 3, 10) == "많음"
    assert diagnose._supply_level_count(6, 3, 10) == "보통"
    # radius=2000m: scale=4 → low=12, high=40
    assert diagnose._supply_level_count(10, 3, 10, 2000) == "적음"
    assert diagnose._supply_level_count(45, 3, 10, 2000) == "많음"
    assert diagnose._supply_level_count(25, 3, 10, 2000) == "보통"


def test_verdict_matrix_and_unknown() -> None:
    assert "부족" in diagnose._verdict("높음", "적음")
    assert "과잉" in diagnose._verdict("낮음", "많음")
    assert "수요 불명" in diagnose._verdict("불명", "보통")


# ── 전체 흐름 (stats·facilities 모킹 — 네트워크 없음) ─────────────────────
def _fake_facts(*_a, **_k):
    facts = [
        {"item": "유소년인구비율", "value": 8.3, "national_avg": 10.3, "unit": "%",
         "source_tbl": "DT_1B04005N", "year": 2025},
        {"item": "고령인구비율", "value": 24.0, "national_avg": 21.2, "unit": "%",
         "source_tbl": "DT_1B04005N", "year": 2025},
        {"item": "1인가구비율", "value": 45.1, "national_avg": 36.1, "unit": "%",
         "source_tbl": "DT_1JC1511", "year": 2024},
        {"item": "생산가능인구비율", "value": 72.5, "national_avg": 68.5, "unit": "%",
         "source_tbl": "DT_1B04005N", "year": 2025},
    ]
    return facts, [], 2025


# 의료시설·초등학교·문화시설 수급 규칙이 추가된 mock band
_MOCK_BAND = {
    "어린이집": 2, "유치원": 1,
    "경로당": 15, "노인복지관": 1,
    "편의점": 30, "코인세탁": 4,
    "병원": 5, "의원": 10, "약국": 8,   # 합계 23 → 보통(10<23<30)
    "초등학교": 1,                        # 보통(0<1<3)
    "도서관": 4, "미술관": 1, "박물관": 1, "문화센터": 2, "공연장": 1, "영화관": 1,  # 합계 10 → 보통(2<10<12)
}


def _fake_facility_result(address, kinds, radii, client=None, loc=None):
    return FacilityResult(
        center=Center(lat=37.52, lon=126.92, address="서울 영등포구 (모의)"),
        results=[],
        counts={str(radii[0]): _MOCK_BAND},
        source="kakao",
        base_date="2026-06-25",
        notes=[],
    )


class _FakeLoc:
    lat, lon = 37.52, 126.92
    address = "서울 영등포구 여의대로 24"
    sgg_code = "11560"
    sigungu = "영등포구"
    notes: list = []


def _fake_childcare(*_a, **_k):
    return {"count": 50, "total_capacity": 2785, "sample": [], "scope": "영등포구"}, []


def test_build_diagnosis_crosses_demand_and_supply(monkeypatch) -> None:
    monkeypatch.setattr(diagnose, "resolve_address", lambda *a, **k: _FakeLoc())
    monkeypatch.setattr(diagnose.stats, "collect_facts_by_items", _fake_facts)
    monkeypatch.setattr(diagnose, "build_facility_result", _fake_facility_result)
    monkeypatch.setattr(diagnose.childcare, "fetch_childcare", _fake_childcare)
    monkeypatch.setattr(diagnose, "fetch_total_pop", lambda *a, **k: 371362)

    res = diagnose.build_diagnosis("서울 영등포구 여의대로 24", radius=1000)

    assert res.region.name == "영등포구"
    assert res.radius == 1000
    assert res.source == "kakao+kosis"
    assert len(res.diagnoses) == 6
    # 모든 진단 '참고' (판단은 사람 — 절대 원칙 5)
    assert all(d.tag == "참고" for d in res.diagnoses)

    by_name = {d.name: d for d in res.diagnoses}
    # 보육: 유소년 8.3 < 10.3-1 → 낮음, 어린이집2+유치원1=3 ≤ low_max3 → 적음
    boyuk = by_name["보육시설 수급"]
    assert boyuk.demand.level == "낮음"
    assert boyuk.supply.count == 3 and boyuk.supply.level == "적음"
    # 어린이집 정원(시군구) 보강 — 반경 개수와 별개 참고수치 (절대 원칙 4)
    assert boyuk.supply.capacity == 2785
    assert boyuk.supply.capacity_scope == "영등포구"
    assert "정원 2785명" in boyuk.note
    # 노인: 고령 24 > 21.2+2 → 높음, 경로당15+노인복지관1=16 ≥ high_min12 → 많음
    noin = by_name["노인복지시설 수급"]
    assert noin.demand.level == "높음" and noin.supply.level == "많음"
    # 1인가구: 45.1 > 36.1+3 → 높음, 편의점30+코인세탁4=34 ≥ 20 → 많음
    solo = by_name["1인가구 생활시설 수급"]
    assert solo.demand.level == "높음"
    assert solo.supply.count == 34
    # 의료: 고령 24 > 21.2+2 → 높음, 병원5+의원10+약국8=23, 10<23<30 → 보통
    medical = by_name["의료시설 수급"]
    assert medical.demand.level == "높음" and medical.supply.level == "보통"
    assert medical.supply.count == 23
    # 초등학교: 유소년 8.3 < 10.3-1 → 낮음, 초등학교 1개, 0<1<3 → 보통
    school = by_name["초등학교 수급"]
    assert school.demand.level == "낮음" and school.supply.level == "보통"
    assert school.supply.count == 1
    # 문화: 생산가능 72.5 > 68.5+2 → 높음, 문화시설 합계 10개, 2<10<12 → 보통
    culture = by_name["문화시설 수급"]
    assert culture.demand.level == "높음" and culture.supply.level == "보통"
    assert culture.supply.count == 10
    assert culture.demand.item == "생산가능인구비율"
    # 원수치가 소견에 인용되는지 (재료·근거 제시)
    assert "8.3%" in boyuk.note and "전국 10.3%" in boyuk.note


def test_build_diagnosis_skips_missing_demand_item(monkeypatch) -> None:
    # 수요지표 facts 가 비면 해당 규칙은 정직하게 건너뛰고 notes 기록 (절대 원칙 3)
    monkeypatch.setattr(diagnose, "resolve_address", lambda *a, **k: _FakeLoc())
    monkeypatch.setattr(diagnose.stats, "collect_facts_by_items", lambda *a, **k: ([], [], None))
    monkeypatch.setattr(diagnose, "build_facility_result", _fake_facility_result)
    monkeypatch.setattr(diagnose.childcare, "fetch_childcare", _fake_childcare)
    monkeypatch.setattr(diagnose, "fetch_total_pop", lambda *a, **k: None)

    res = diagnose.build_diagnosis("서울 영등포구 여의대로 24", radius=1000)
    assert res.diagnoses == []
    assert any("데이터 없음" in n for n in res.notes)


# ── 라이브 (키 있을 때만) ────────────────────────────────────────────────
@pytest.mark.skipif(
    not (os.getenv("KOSIS_KEY") and os.getenv("KAKAO_KEY")),
    reason="KOSIS_KEY/KAKAO_KEY 미설정 — 실호출 skip",
)
def test_diagnose_endpoint_real() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    r = client.post("/diagnose", json={"address": "서울 영등포구 여의대로 24", "radius": 1000})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["region"]["code"] == "11560"
    assert len(body["diagnoses"]) >= 1
    for d in body["diagnoses"]:
        assert d["tag"] == "참고"
        assert isinstance(d["demand"]["value"], (int, float))
        assert isinstance(d["supply"]["count"], int)
