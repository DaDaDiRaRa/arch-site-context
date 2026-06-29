"""어린이집 현황 실호출 테스트 (정보공개포털) — 키·네트워크 있을 때만.

cpmsapi021 + CHILDCARE_INFO_KEY + arcode(시군구 5자리). 미설정/오류는 graceful skip.
검증된 엔드포인트([[childcare-culture-api]]) 기반.
"""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

load_dotenv()


@pytest.mark.skipif(
    not os.getenv("CHILDCARE_INFO_KEY"), reason="CHILDCARE_INFO_KEY 미설정"
)
def test_childcare_yeongdeungpo() -> None:
    from app.services import childcare

    d, notes = childcare.fetch_childcare("11560", "영등포구")
    if d is None:
        pytest.skip(f"어린이집 응답 없음: {notes}")
    assert d["count"] > 0
    assert d["total_capacity"] > 0
    assert d["scope"] == "영등포구"
    assert d["sample"]


def test_childcare_bad_code() -> None:
    """5자리 시군구코드 아니면 추정 없이 건너뜀 (절대 원칙 3)."""
    from app.services import childcare

    d, notes = childcare.fetch_childcare("11")
    assert d is None
    assert notes and "형식 오류" in notes[0]
