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
def test_site_hazards_membership() -> None:
    from app.services import sgis

    # 여의도(한강 섬) — 홍수 영향범위 포함 기대
    h = sgis.fetch_site_hazards(37.5221803249647, 126.919916550827)
    assert h is not None
    assert h["emd_cd"] and len(h["emd_cd"]) == 8
    assert h["flood"]["in_zone"] is True  # 한강 인접 → 홍수 영향범위
    # 포함여부는 bool, 영향 동수는 양수
    for key in ("flood", "landslide"):
        assert h[key]["in_zone"] in (True, False)
        assert h[key]["affected_dong_count"] >= 0
    # 영향범위 내 지표(인구·가구·주택·사업체) — 읍면동 우선·시군구 폴백
    fl = h["flood"]
    assert isinstance(fl["exposures"], list) and fl["exposures"]  # 홍수 포함이므로 비지 않음
    metrics = {e["metric"] for e in fl["exposures"]}
    assert "인구" in metrics
    if fl["exposures"]:
        assert fl["exposure_scope"] in ("읍면동", "시군구")
    for e in fl["exposures"]:
        if e["affected"] is not None and e["total"] is not None:
            assert e["total"] >= e["affected"]  # 영향 ≤ 전체
    assert h["source"] == "sgis"


@pytest.mark.skipif(not _HAS_KEY, reason="SGIS_KEY/SGIS_SECRET 미설정 — 실호출 skip")
def test_heatwave_history() -> None:
    from app.services import sgis

    h = sgis.fetch_heatwave_history("서울", "영등포구")
    assert h is not None
    assert h["alert_count"] >= 0 and h["warning_count"] >= 0
    # 서울은 권역 단위 → 광역 scope, 여름 폭염 기록 있음 (2024~2025)
    assert h["alert_count"] + h["warning_count"] > 0
    assert "여름" in h["base_period"]
    # 비서울 시군구는 시군구로 좁혀짐
    g = sgis.fetch_heatwave_history("경기", "과천시")
    assert g and g["scope"] == "과천시"


@pytest.mark.skipif(not _HAS_KEY, reason="SGIS_KEY/SGIS_SECRET 미설정 — 실호출 skip")
def test_radius_grows_with_radius() -> None:
    from app.services import sgis

    small = sgis.fetch_radius_population(37.5221803249647, 126.919916550827, 500)
    big = sgis.fetch_radius_population(37.5221803249647, 126.919916550827, 2000)
    assert small and big
    # 반경이 커지면 집계구 수·인구 증가 (실데이터 합산이므로 단조)
    assert big["total_pop"] > small["total_pop"]
    assert big["tong_count"] > small["tong_count"]
