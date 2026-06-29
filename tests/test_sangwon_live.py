"""상권(상가업소) 분포 실호출 테스트 — DATA_GO_KR 키·네트워크 있을 때만.

SBIZ365 #29·#30 재분류(§8.7): SBIZ365 는 REST API 없음(대시보드/파일만).
점포 '분포'의 정식 실API 는 B553077 상가(상권)정보 뿐 → sangwon.py 로 승격.
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


def test_store_district() -> None:
    from app.services import sangwon

    d, notes = sangwon.fetch_store_district(37.5260, 126.9244, 500)
    if d is None:
        pytest.skip(f"상권 데이터 없음/오류: {notes}")

    assert d["total"] > 0
    assert d["by_large"]  # 업종 대분류별 집계
    # 집계 합 == 수집 건수 (코드 계산 정합)
    assert sum(c for _, c in d["by_large"]) == d["fetched"]
    assert d["radius"] == 500
