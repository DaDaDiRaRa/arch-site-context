"""site_seed 공통 빌더 테스트 — 키·네트워크 있을 때만 (P12 연결 준비).

build_site: 주소 → 공유 Site(좌표·코드·PNU). build_project_seed: 보드 골격.
"""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

load_dotenv()

pytestmark = pytest.mark.skipif(
    not os.getenv("KAKAO_KEY"), reason="KAKAO_KEY 미설정 — 실호출 skip"
)


def test_build_site() -> None:
    from app.services.kakao import KakaoError
    from app.services.site_seed import build_site

    try:
        site = build_site("서울특별시 영등포구 여의대로 24")
    except KakaoError as e:
        pytest.skip(f"주소 해석 실패: {e}")

    assert 33.0 <= site.lat <= 39.0
    assert 124.0 <= site.lon <= 132.0
    assert site.sgg_code == "11560"
    assert site.bcode and site.bcode.startswith("11560")
    # PNU 는 VWorld 키 있으면 채워짐(19자리), 없으면 빈 문자열 허용
    if os.getenv("VWORLD_KEY") and site.pnu:
        assert len(site.pnu) == 19


def test_build_site_without_pnu() -> None:
    from app.services.kakao import KakaoError
    from app.services.site_seed import build_site

    try:
        site = build_site("서울특별시 영등포구 여의대로 24", with_pnu=False)
    except KakaoError as e:
        pytest.skip(f"주소 해석 실패: {e}")
    assert site.pnu == ""


def test_build_project_seed_skeleton() -> None:
    from app.services.kakao import KakaoError
    from app.services.site_seed import build_project_seed

    try:
        seed = build_project_seed(
            "서울특별시 영등포구 여의대로 24", with_pnu=False, base_date="2026-06-29"
        )
    except KakaoError as e:
        pytest.skip(f"주소 해석 실패: {e}")

    assert seed.site.sgg_code == "11560"
    assert seed.base_date == "2026-06-29"
    # 형제 앱 블록은 비어 있음 (각 앱이 채움 — 경계)
    assert seed.law is None and seed.knowledge is None
