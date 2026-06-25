"""모드 A 설정·룩업 테스트 (P4) — 네트워크 불필요, 순수 코드.

완료 기준: /matrix 에 주거 → 항목 목록, 샘플 facts → 룩업대로 '참고' 시사점.
매트릭스·규칙은 JSON 만 고쳐 바뀌어야 하므로 데이터 주도로 검증한다.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.implications import derive_implications
from app.services.matrix import list_items, use_types

client = TestClient(app)


# ── matrix ───────────────────────────────────────────────────
def test_matrix_use_types_present() -> None:
    uts = use_types()
    assert {"주거", "상업", "의료"} <= set(uts)
    assert "_meta" not in uts  # 메타키 제외


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
