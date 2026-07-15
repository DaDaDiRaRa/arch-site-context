"""모드 A 설정·룩업 테스트 (P4) — 네트워크 불필요, 순수 코드.

완료 기준: /matrix 에 주거 → 항목 목록, 샘플 facts → 룩업대로 '참고' 시사점.
매트릭스·규칙은 JSON 만 고쳐 바뀌어야 하므로 데이터 주도로 검증한다.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.implications import derive_implications
from app.services.matrix import list_items, resolve_profile, use_types

client = TestClient(app)


# ── matrix ───────────────────────────────────────────────────
def test_matrix_use_types_present() -> None:
    uts = use_types()
    assert {"주거", "상업", "의료", "복합", "공공", "교육", "복지"} <= set(uts)
    assert "_meta" not in uts  # 메타키 제외


# ── 2계층 용도 매핑 (법적 용도 → 분석 프로파일) ──────────────────
def test_resolve_profile_maps_legal_uses() -> None:
    # 법적 용도(건축법 별표1) → 프로파일
    assert resolve_profile("공동주택") == "주거"
    assert resolve_profile("업무시설") == "상업"
    assert resolve_profile("노유자시설") == "복지"
    assert resolve_profile("교육연구시설") == "교육"
    # 프로파일 자체는 그대로
    assert resolve_profile("주거") == "주거"
    # 알 수 없는 용도 → None (하드블록 대상, 절대 원칙 3)
    assert resolve_profile("우주정거장") is None
    assert resolve_profile(None) is None


def test_list_items_accepts_legal_use() -> None:
    # 법적 용도로도 프로파일 항목이 나온다 (list_items 내부 해석)
    residential = {i["item"] for i in list_items("주거")}
    via_legal = {i["item"] for i in list_items("공동주택")}
    assert via_legal == residential and residential  # 동일 + 비어있지 않음
    assert list_items("우주정거장") is None  # 알 수 없는 용도


def test_use_types_catalog_endpoint() -> None:
    r = client.get("/use-types")
    assert r.status_code == 200
    cat = r.json()
    assert {"주거", "교육", "복지"} <= set(cat["profiles"])
    assert cat["map"]["공동주택"] == "주거"
    assert "숙박시설" in cat["data_limited"]  # 데이터 한정
    groups = {g["group"] for g in cat["groups"]}
    assert "주거" in groups and "산업·특수 (데이터 한정)" in groups


def test_matrix_education_welfare_items() -> None:
    edu = {i["item"] for i in list_items("교육")}
    assert "유소년인구비율" in edu  # 학령 수요 핵심
    wel = {i["item"] for i in list_items("복지")}
    assert {"고령인구비율", "노년부양비", "1인가구비율"} <= wel


def test_matrix_public_items() -> None:
    # P16: 공공(공공청사·문화·복지) — 수혜 배후·연령·복지 수요 항목
    names = {i["item"] for i in list_items("공공")}
    assert {"총인구수", "고령인구비율", "유소년인구비율", "1인가구비율", "노년부양비"} <= names


def test_implications_fire_for_public() -> None:
    # 공공: 노년부양비(돌봄 동선)·1인가구(생활지원 커뮤니티) 함의 발화
    facts = [
        {"item": "노년부양비", "value": 30.0, "national_avg": 22.0, "unit": "%"},
        {"item": "1인가구비율", "value": 40.0, "national_avg": 33.0, "unit": "%"},
    ]
    imps = derive_implications(facts, use_type="공공")
    bases = {i["basis"] for i in imps}
    assert "노년부양비" in bases and "1인가구비율" in bases
    assert any("커뮤니티" in i["text"] for i in imps)  # 공공 전용 규칙
    assert all(i["tag"] == "참고" for i in imps)


def test_matrix_mixed_use_items() -> None:
    # P16: 복합(주상복합) — 주거(가구·연령) + 상업(배후·활동인구) 항목 재조합
    names = {i["item"] for i in list_items("복합")}
    assert {"총인구수", "생산가능인구비율", "1인가구비율", "고령인구비율", "순이동", "세대수"} <= names


def test_implications_fire_for_mixed_use() -> None:
    # 복합 용도에서 주거·상업 함의가 함께 발화 + 복합 전용(생산가능인구) 함의
    facts = [
        {"item": "1인가구비율", "value": 40.0, "national_avg": 33.0, "unit": "%"},      # 소형·공유
        {"item": "생산가능인구비율", "value": 78.0, "national_avg": 71.0, "unit": "%"},  # 저층부 F&B
    ]
    imps = derive_implications(facts, use_type="복합")
    bases = {i["basis"] for i in imps}
    assert "1인가구비율" in bases and "생산가능인구비율" in bases
    assert any("저층부" in i["text"] for i in imps)
    assert all(i["tag"] == "참고" for i in imps)


def test_matrix_endpoint_residential() -> None:
    r = client.get("/matrix", params={"use_type": "주거"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 1
    names = [i["item"] for i in items]
    assert "고령인구비율" in names
    # 항목 계약 필드 존재 (KOSIS 파라미터는 kosis 블록으로 이동)
    for i in items:
        assert {"item", "method", "priority", "min_resolution", "freq"} <= set(i)


def test_matrix_min_priority_filters() -> None:
    only1 = list_items("주거", min_priority=1)
    all3 = list_items("주거", min_priority=3)
    assert all(i["priority"] == 1 for i in only1)
    assert len(only1) <= len(all3)
    # priority 오름차순 정렬
    prios = [i["priority"] for i in all3]
    assert prios == sorted(prios)


def test_matrix_unknown_use_type_404() -> None:
    r = client.get("/matrix", params={"use_type": "없는용도"})
    assert r.status_code == 404


# ── implications 룩업 ────────────────────────────────────────
def test_implications_lookup_triggers() -> None:
    # 고령인구비율 전국평균보다 +5p 초과 → 무장애 동선 규칙 발동 (주거)
    facts = [
        {"item": "고령인구비율", "value": 22.0, "national_avg": 16.0, "unit": "%"},
        {"item": "1인가구비율", "value": 40.0, "national_avg": 33.0, "unit": "%"},
    ]
    imps = derive_implications(facts, use_type="주거")
    bases = {i["basis"] for i in imps}
    assert "고령인구비율" in bases  # +6 > margin 5
    assert "1인가구비율" in bases   # +7 > margin 3
    assert all(i["tag"] == "참고" for i in imps)


def test_implications_no_trigger_when_below_margin() -> None:
    # 차이가 margin 이하 → 발동 안 함
    facts = [{"item": "고령인구비율", "value": 17.0, "national_avg": 16.0, "unit": "%"}]
    imps = derive_implications(facts, use_type="주거")
    assert all(i["basis"] != "고령인구비율" for i in imps)


def test_implications_respects_use_type() -> None:
    # 노년부양비 규칙은 의료 전용 → 주거에선 안 나오고 의료에선 나온다
    facts = [{"item": "노년부양비", "value": 30.0, "national_avg": 22.0, "unit": "%"}]
    assert not any(i["basis"] == "노년부양비" for i in derive_implications(facts, "주거"))
    assert any(i["basis"] == "노년부양비" for i in derive_implications(facts, "의료"))


def test_implications_less_than_operator() -> None:
    # 1인가구비율이 전국평균보다 충분히 낮으면 가족단위 규칙(op '<') 발동
    facts = [{"item": "1인가구비율", "value": 25.0, "national_avg": 33.0, "unit": "%"}]
    imps = derive_implications(facts, use_type="주거")
    texts = " ".join(i["text"] for i in imps)
    assert "중대형" in texts


def test_implications_missing_national_avg_skipped() -> None:
    # 비교기준(national_avg) 없으면 추정 안 하고 건너뜀 (절대 원칙 3)
    facts = [{"item": "고령인구비율", "value": 99.0, "national_avg": None, "unit": "%"}]
    assert derive_implications(facts, "주거") == []
