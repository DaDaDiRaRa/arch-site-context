"""에어코리아 대기질 실호출 테스트 — DATA_GO_KR 키·네트워크 있을 때만.

§8.7 버그수정 검증: getMsrstnList(미승인 측정소검색) 의존 제거,
시도 전체 측정값(getCtprvnRltmMesureDnsty)에서 시군구명 매칭.
미승인(403)/미일치 시 graceful 빈값 (절대 원칙 3).
"""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

load_dotenv()

pytestmark = pytest.mark.skipif(
    not os.getenv("DATA_GO_KR_API_KEY"),
    reason="DATA_GO_KR_API_KEY 미설정 — 실호출 skip",
)


def test_air_quality_seoul_gu() -> None:
    """서울 구 단위 — 동명 측정소 매칭으로 PM2.5 등 실데이터."""
    from app.services import airkorea

    facts, notes = airkorea.fetch_air_quality("서울특별시", "영등포구")
    if not facts:
        pytest.skip(f"미승인/결측으로 skip: {notes}")

    items = {f["item"] for f in facts}
    assert any("PM2.5" in i for i in items)
    for f in facts:
        assert isinstance(f["value"], float)
        assert f["source_type"] == "airkorea"
        assert "영등포" in f["source_tbl"]


def test_air_quality_no_match_skips() -> None:
    """일치 측정소 없으면 임의 대체 없이 건너뜀 (절대 원칙 3)."""
    from app.services import airkorea

    facts, notes = airkorea.fetch_air_quality("경기도", "가평군")
    # 가평 측정소가 없으면 빈값 + 정직한 note (있으면 매칭되어 facts 반환 — 둘 다 정상)
    if not facts:
        assert notes and ("없음" in notes[0] or "건너뜀" in notes[0])
