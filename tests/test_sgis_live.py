"""SGIS 반경 인구 라이브 테스트 (D2) — 키 있을 때만 (skipif).

좌표+반경 → 집계구 합산 실인구. 보간 아님 (절대 원칙 1·3).
"""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

load_dotenv()

_HAS_KEY = bool(os.getenv("SGIS_KEY") and os.getenv("SGIS_SECRET"))


@pytest.mark.skipif(not _HAS_KEY, reason="SGIS_KEY/SGIS_SECRET 미설정 — 실호출 skip")
def test_radius_population_yeouido() -> None:
    from app.services import sgis

    r = sgis.fetch_radius_population(37.5221803249647, 126.919916550827, 1000)
    assert r is not None
    # 반경 내 실인구 (집계구 합산)
    assert r["total_pop"] > 0
    assert r["tong_matched"] >= 1
    assert r["tong_matched"] <= r["tong_count"]
    # 연령비율 역산 (0~100, 합 ≈ 100)
    for k in ("youth_share", "aged_share", "working_share"):
        assert r[k] is None or 0 <= r[k] <= 100
    s = sum(v for k in ("youth_share", "aged_share", "working_share") if (v := r[k]) is not None)
    assert 99.0 <= s <= 101.0  # 반올림 오차 허용
    assert r["source"] == "sgis"


@pytest.mark.skipif(not _HAS_KEY, reason="SGIS_KEY/SGIS_SECRET 미설정 — 실호출 skip")
def test_radius_grows_with_radius() -> None:
    from app.services import sgis

    small = sgis.fetch_radius_population(37.5221803249647, 126.919916550827, 500)
    big = sgis.fetch_radius_population(37.5221803249647, 126.919916550827, 2000)
    assert small and big
    # 반경이 커지면 집계구 수·인구 증가 (실데이터 합산이므로 단조)
    assert big["total_pop"] > small["total_pop"]
    assert big["tong_count"] > small["tong_count"]
