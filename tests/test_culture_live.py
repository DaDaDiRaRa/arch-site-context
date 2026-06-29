"""문화기반시설총람 실호출 테스트 (data.go.kr B553457) — 키·네트워크 있을 때만.

10개 시설유형 operation + DATA_GO_KR_API_KEY + pblshYr(자동탐지) + sggCd.
여러 시군구로 검증(특정 지역 일반화 금지). 미승인/오류는 graceful skip.
검증된 엔드포인트([[childcare-culture-api]]) 기반.
"""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

load_dotenv()

pytestmark = pytest.mark.skipif(
    not os.getenv("DATA_GO_KR_API_KEY"), reason="DATA_GO_KR_API_KEY 미설정"
)


@pytest.mark.parametrize(
    "sgg, name",
    [("11110", "종로구"), ("11680", "강남구"), ("11560", "영등포구")],
)
def test_culture_multiple_districts(sgg: str, name: str) -> None:
    from app.services import culture

    d, notes = culture.fetch_culture(sgg, name)
    if d is None:
        pytest.skip(f"문화시설 응답 없음({name}): {notes}")
    assert d["total"] > 0
    assert d["by_type"]  # 시설유형별 카운트
    assert d["scope"] == name
    assert d["pblshYr"]  # 발간연도 확정
    # 시설명·유형이 채워졌는지
    if d["sample"]:
        assert d["sample"][0]["name"]
        assert d["sample"][0]["type"] in d["by_type"]


def test_culture_bad_code() -> None:
    """5자리 시군구코드 아니면 추정 없이 건너뜀 (절대 원칙 3)."""
    from app.services import culture

    d, notes = culture.fetch_culture("11")
    assert d is None
    assert notes and "형식 오류" in notes[0]
