"""주소 해석 단위/통합 테스트 (P1.6).

순수 헬퍼(법정동→시군구코드)는 네트워크 없이, 실호출은 키 있을 때만.
"""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

from app.services.resolve import _sgg_from_bcode

load_dotenv()


# ── 순수 헬퍼 (네트워크 불필요) ──────────────────────────────
def test_sgg_from_bcode() -> None:
    assert _sgg_from_bcode("1156011000") == "11560"  # 영등포구
    assert _sgg_from_bcode("4113510300") == "41135"  # 성남시 분당구
    assert _sgg_from_bcode("") == ""
    assert _sgg_from_bcode("123") == ""  # 5자리 미만은 빈값


# ── 실호출 (키 있을 때만) ────────────────────────────────────
_has_kakao = bool(os.getenv("KAKAO_KEY"))
_has_juso = bool(os.getenv("JUSO_API_KEY"))


@pytest.mark.skipif(not _has_juso, reason="JUSO_API_KEY 미설정")
def test_juso_live() -> None:
    from app.services import juso

    try:
        res = juso.search_address("영등포구 여의대로 24")
    except juso.JusoError as e:
        pytest.skip(f"JUSO 네트워크/키 문제: {e}")
    assert res is not None
    assert res["adm_cd"].startswith("1156")  # 영등포구 법정동코드
    assert "영등포구" in res["sigungu"]


@pytest.mark.skipif(not _has_kakao, reason="KAKAO_KEY 미설정")
def test_resolve_live() -> None:
    from app.services.kakao import KakaoError
    from app.services.resolve import resolve_address

    try:
        loc = resolve_address("서울 영등포구 여의대로 24")
    except KakaoError as e:
        pytest.skip(f"네트워크/키 문제: {e}")

    # WGS84 (대한민국 범위)
    assert 33.0 <= loc.lat <= 39.0
    assert 124.0 <= loc.lon <= 132.0
    # 법정동코드 10자리 + 시군구코드 5자리 정합
    assert len(loc.bcode) == 10
    assert loc.sgg_code == loc.bcode[:5] == "11560"
    assert loc.sigungu == "영등포구"
    assert "kakao" in loc.source
