"""모드 A /analyze 실호출 + 캐시 테스트 (P5).

KOSIS/카카오 키·네트워크 있을 때만. 완료 기준:
- 실제 주소+용도로 facts 가 실수치로 채워진다 (source_tbl·year 명시).
- 같은 (지역,항목,연도) 재호출 시 캐시 히트 = 네트워크 0콜.
"""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

load_dotenv()

pytestmark = pytest.mark.skipif(
    not (os.getenv("KOSIS_KEY") and os.getenv("KAKAO_KEY")),
    reason="KOSIS_KEY/KAKAO_KEY 미설정 — 실호출 skip",
)


def test_collect_facts_real_and_cache_hit() -> None:
    from app.services import kosis
    from app.services.cache import MemoryCache
    from app.services.stats import collect_facts

    cache = MemoryCache()

    # 1차: 네트워크 호출 발생
    before = kosis.NETWORK_CALLS
    facts, notes, year = collect_facts("11560", "주거", year=None, cache=cache)
    first_calls = kosis.NETWORK_CALLS - before

    assert len(facts) >= 1, "실수치 facts 가 채워져야 함"
    assert first_calls >= 1, "첫 호출은 네트워크가 일어나야 함"

    # 각 fact 계약: 실수치 + 출처/연도 명시
    for f in facts:
        assert isinstance(f["value"], (int, float))
        assert f["source_tbl"] and f["year"]
        assert f["unit"] is not None

    # 고령인구비율은 합리적 범위(0~100)
    aged = [f for f in facts if f["item"] == "고령인구비율"]
    if aged:
        assert 0 <= aged[0]["value"] <= 100
        assert aged[0]["national_avg"] is not None  # 전국 비교 존재

    # 2차: 동일 요청(year=None 그대로) → 캐시 히트, 네트워크 0콜
    before2 = kosis.NETWORK_CALLS
    facts2, _, _ = collect_facts("11560", "주거", year=None, cache=cache)
    assert kosis.NETWORK_CALLS - before2 == 0, "재호출은 캐시 히트로 0콜이어야 함"
    assert len(facts2) == len(facts)


def test_analyze_endpoint_real() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    r = client.post("/analyze", json={"address": "서울 영등포구 여의대로 24", "use_type": "의료"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["region"]["code"] == "11560"
    assert body["region"]["resolution"] == "시군구"
    assert len(body["facts"]) >= 1
    # 함의는 '참고' 태그
    assert all(i["tag"] == "참고" for i in body["implications"])
    # '○○구 기준' 표기
    assert "기준" in body["draft_paragraph"]


def test_analyze_unknown_use_type_errorblock() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    r = client.post("/analyze", json={"address": "서울 영등포구 여의대로 24", "use_type": "없는용도"})
    assert r.status_code == 422
    assert r.json()["code"] == "NO_DATA"
